from psychopy import visual, core, event, gui
from datetime import datetime
import time
import csv
import os
import re
import ctypes

# ============================================================
# RESTING STATE TASK
# 10-minute eyes-closed resting-state recording
# ============================================================

# -------------------------
# Settings
# -------------------------

TASK_NAME = "resting_state"
TASK_DURATION_SEC = 10 * 60  # 10 minutes

FULLSCREEN = True  # Change to True for real data collection

# -------------------------
# Low-Level Parallel Port Initialization (via ctypes)
# -------------------------
# Explicit path to your dedicated test driver subfolder
DLL_DIR = r"C:\Users\mindlab\Documents\PsychoPy\Test Tasks\IO"
dll_64_path = os.path.join(DLL_DIR, "inpoutx64.dll")

io_driver = None
PORT_ADDRESS = 0x3FF8  # Verified hardware port address

try:
    if os.path.exists(dll_64_path):
        io_driver = ctypes.windll.LoadLibrary(dll_64_path)
        print(f"EEG parallel port driver loaded successfully from: {dll_64_path}")
    else:
        print(f"Warning: inpoutx64.dll not found in specified folder: {DLL_DIR}")
except Exception as e:
    print(f"Warning: Failed to load EEG parallel port driver: {e}")

# -------------------------
# Helper functions
# -------------------------

def send_trigger(code):
    """
    Sends a 5ms TTL pulse to the physical parallel port pins for EEG marking.
    """
    if io_driver is not None:
        try:
            io_driver.Out32(PORT_ADDRESS, code)
            core.wait(0.005)  # 5ms pulse width
            io_driver.Out32(PORT_ADDRESS, 0)     # Clear pins back to baseline
        except Exception as e:
            print(f"Failed to send hardware trigger {code}: {e}")
    else:
        print(f"[Mock Trigger] Sent code: {code}")


def clean_participant_number(value):
    value = str(value).strip()
    if not value or value.lower() == "test": return "TEST"
    digits = re.sub(r"\D", "", value)
    return digits.zfill(3) if digits else "TEST"


def clean_visit(value):
    value = str(value).strip().upper()
    if not value or value in ["B", "W2", "W4", "W6", "W8", "TEST"]: return value or "TEST"
    return value.replace(" ", "")


def clean_block(value):
    value = str(value).strip()
    if not value: return "RestingState"
    value = re.sub(r"[^A-Za-z0-9_-]", "", value)
    return value or "RestingState"


def clean_date(value):
    value = str(value).strip()
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 8 else datetime.now().strftime("%Y%m%d")


# -------------------------
# Participant / session dialog
# -------------------------

today_yyyymmdd = datetime.now().strftime("%Y%m%d")

exp_info = {
    "participant_number": "001",
    "visit": "B",
    "block": "RestingState",
    "date_YYYYMMDD": today_yyyymmdd
}

dlg = gui.DlgFromDict(dictionary=exp_info, title="Resting-State Task")
if not dlg.OK: core.quit()

participant_number = clean_participant_number(exp_info["participant_number"])
visit = clean_visit(exp_info["visit"])
block = clean_block(exp_info["block"])
date_yyyymmdd = clean_date(exp_info["date_YYYYMMDD"])
file_stem = f"MLI{participant_number}_{visit}_{block}_{date_yyyymmdd}"

output_dir = "data"
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, f"{file_stem}.csv")

win = visual.Window(size=(1200, 800), fullscr=FULLSCREEN, color="black", units="height")

# -------------------------
# Stimuli
# -------------------------

instructions = visual.TextStim(
    win,
    text=(
        "Resting-State Recording\n\n"
        "Please sit comfortably and keep your eyes closed for the entire duration of this block.\n\n"
        "You do not need to do anything in particular with your mind.\n"
        "You also do not need to prevent your mind from doing anything.\n\n"
        "Simply remain still, relaxed, and awake until the recording is complete.\n\n"
        "Researcher: press SPACE to begin."
    ),
    color="white", height=0.04, wrapWidth=1.25
)

fixation = visual.TextStim(win, text="+", color="white", height=0.08)

# -------------------------
# Instruction screen
# -------------------------

instructions.draw()
win.flip()

keys = event.waitKeys(keyList=["space", "escape"])
if "escape" in keys:
    win.close()
    core.quit()

# -------------------------
# Start resting-state block
# -------------------------

send_trigger(101)  # EEG Trigger: Resting-state start

task_start_clock = core.Clock()
task_start_iso = datetime.now().isoformat()
task_start_unix_sec = time.time()

fixation.draw()
win.flip()

while task_start_clock.getTime() < TASK_DURATION_SEC:
    keys = event.getKeys(keyList=["escape"])
    if "escape" in keys: break
    core.wait(0.1)

task_end_iso = datetime.now().isoformat()
task_end_unix_sec = time.time()
actual_duration_sec = task_start_clock.getTime()

send_trigger(102)  # EEG Trigger: Resting-state end

# -------------------------
# Save minimal task log
# -------------------------

with open(output_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "file_stem", "participant_id", "participant_number", "visit", "block",
            "date_YYYYMMDD", "task_name", "planned_duration_sec", "actual_duration_sec",
            "task_start_iso", "task_end_iso", "task_start_unix_sec", "task_end_unix_sec", "completed"
        ]
    )
    writer.writeheader()
    writer.writerow({
        "file_stem": file_stem, "participant_id": f"MLI{participant_number}", "participant_number": participant_number,
        "visit": visit, "block": block, "date_YYYYMMDD": date_yyyymmdd, "task_name": TASK_NAME,
        "planned_duration_sec": TASK_DURATION_SEC, "actual_duration_sec": round(actual_duration_sec, 3),
        "task_start_iso": task_start_iso, "task_end_iso": task_end_iso,
        "task_start_unix_sec": round(task_start_unix_sec, 6), "task_end_unix_sec": round(task_end_unix_sec, 6),
        "completed": int(actual_duration_sec >= TASK_DURATION_SEC)
    })

win.close()
core.quit()
