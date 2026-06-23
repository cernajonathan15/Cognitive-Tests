from psychopy import visual, core, event, gui
from datetime import datetime
import time
import csv
import os
import re
import ctypes

# ============================================================
# OPEN MONITORING MEDITATION TASK
# 10-minute eyes-closed meditation block
# Records red/right response-pad presses mapped to keyboard "4"
# ============================================================

# -------------------------
# Settings
# -------------------------

TASK_NAME = "open_monitoring"
MEDITATION_TYPE = "OpenMonitoring"
TASK_DURATION_SEC = 10 * 60  # 10 minutes

FULLSCREEN = True  # Change to False only for testing on a single monitor

# Hardware Response Mapping
# In your existing code, the red/right response-pad button maps to "4".
RESPONSE_KEY = "4"
QUIT_KEY = "escape"
DEBOUNCE_SEC = 0.25  # prevents duplicate logs from button bounce or long holds

# EEG Trigger Codes
# These are distinct from the existing resting-state and motor-control triggers.
TRIGGERS = {
    "task_start": 245,
    "mind_wandering_button": 205,
    "task_end": 235,
}

# -------------------------
# Low-Level Parallel Port Initialization (via ctypes)
# -------------------------
# Same driver folder and port address used in the current task files.
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
            io_driver.Out32(PORT_ADDRESS, 0)  # Clear pins back to baseline
        except Exception as e:
            print(f"Failed to send hardware trigger {code}: {e}")
    else:
        print(f"[Mock Trigger] Sent code: {code}")


def clean_participant_number(value):
    value = str(value).strip()
    if not value or value.lower() == "test":
        return "TEST"
    digits = re.sub(r"\D", "", value)
    return digits.zfill(3) if digits else "TEST"


def clean_visit(value):
    value = str(value).strip().upper()
    if not value or value in ["B", "W2", "W4", "W6", "W8", "TEST"]:
        return value or "TEST"
    return value.replace(" ", "")


def clean_block(value):
    value = str(value).strip()
    if not value:
        return "OpenMonitoring"
    value = re.sub(r"[^A-Za-z0-9_-]", "", value)
    return value or "OpenMonitoring"


def clean_date(value):
    value = str(value).strip()
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 8 else datetime.now().strftime("%Y%m%d")


def get_psychopy_global_time():
    """
    Returns PsychoPy's monotonic global clock time when available.
    This is separate from local wall-clock ISO time and Unix epoch time.
    """
    try:
        return round(core.getTime(), 6)
    except Exception:
        return ""


def make_event_row(
    file_stem, participant_number, visit, block, date_yyyymmdd,
    event_index, event_type, trigger_code, task_clock,
    response_count="", response_key="", response_task_time=None,
    task_start_iso="", task_start_unix_sec="", task_end_iso="",
    task_end_unix_sec="", actual_duration_sec="", completed="", escaped=""
):
    now_iso = datetime.now().isoformat()
    now_unix = time.time()
    task_time_sec = task_clock.getTime() if response_task_time is None else response_task_time

    return {
        "file_stem": file_stem,
        "participant_id": f"MLI{participant_number}",
        "participant_number": participant_number,
        "visit": visit,
        "block": block,
        "date_YYYYMMDD": date_yyyymmdd,
        "task_name": TASK_NAME,
        "meditation_type": MEDITATION_TYPE,
        "event_index": event_index,
        "event_type": event_type,
        "response_count": response_count,
        "response_key": response_key,
        "trigger_code": trigger_code,
        "task_time_sec": round(task_time_sec, 6),
        "psychopy_global_clock_sec": get_psychopy_global_time(),
        "iso_time": now_iso,
        "unix_time_sec": round(now_unix, 6),
        "task_start_iso": task_start_iso,
        "task_start_unix_sec": task_start_unix_sec,
        "task_end_iso": task_end_iso,
        "task_end_unix_sec": task_end_unix_sec,
        "planned_duration_sec": TASK_DURATION_SEC,
        "actual_duration_sec": actual_duration_sec,
        "completed": completed,
        "escaped": escaped,
    }


def wait_for_researcher_space_or_escape():
    keys = event.waitKeys(keyList=["space", QUIT_KEY])
    return False if QUIT_KEY in keys else True


def draw_text_and_wait(win, text_stim):
    text_stim.draw()
    win.flip()
    if not wait_for_researcher_space_or_escape():
        win.close()
        core.quit()


# -------------------------
# Participant / session dialog
# -------------------------

today_yyyymmdd = datetime.now().strftime("%Y%m%d")

exp_info = {
    "participant_number": "001",
    "visit": "B",
    "block": "OpenMonitoring",
    "date_YYYYMMDD": today_yyyymmdd
}

dlg = gui.DlgFromDict(dictionary=exp_info, title="Open Monitoring Task")
if not dlg.OK:
    core.quit()

participant_number = clean_participant_number(exp_info["participant_number"])
visit = clean_visit(exp_info["visit"])
block = clean_block(exp_info["block"])
date_yyyymmdd = clean_date(exp_info["date_YYYYMMDD"])
file_stem = f"MLI{participant_number}_{visit}_{block}_{date_yyyymmdd}"

# -------------------------
# Output setup
# -------------------------

output_dir = "data"
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, f"{file_stem}.csv")

# -------------------------
# Window and stimuli
# -------------------------

win = visual.Window(size=(1200, 800), fullscr=FULLSCREEN, color="black", units="height")

instructions = visual.TextStim(
    win,
    text=(
        "Open Monitoring Meditation\n\n"
        "Please sit comfortably and keep your eyes closed for this entire block.\n\n"
        "For this block, keep all of your senses completely open. Allow sounds, bodily sensations, "
        "thoughts, emotions, and other experiences to arise and pass without trying to control "
        "where your attention goes.\n\n"
        "Whenever you notice that your mind has wandered into being caught up in a thought, feeling, "
        "or experience, press the red/right button once. Then gently return to openly monitoring "
        "everything happening in your sense experience.\n\n"
        "There is no right or wrong number of button presses. The button press simply marks the moment "
        "when you noticed mind wandering and began shifting attention back to open monitoring.\n\n"
        "Please do this non-judgmentally. If the mind wanders, that is completely okay. "
        "Notice it, press the red/right button, and gently return to openly monitoring your experience.\n\n"
        "To help maintain keen awareness, you may use a noting technique. This means silently using "
        "one or two simple words to label what is happening, such as seeing, thinking, hearing, "
        "smelling, or feeling. The labels should use no mental energy. They are only meant to keep "
        "your sense of presence sharp.\n\n"
        "Researcher: press SPACE to begin."
    ),
    color="white",
    height=0.032,
    wrapWidth=1.35,
    pos=(0, 0),
    alignText="center"
)

# CHANGED: Replaced in_progress_text with a standard fixation crosshairs component
fixation = visual.TextStim(win, text="+", color="white", height=0.08)

end_text = visual.TextStim(
    win,
    text="Open Monitoring Meditation Complete\n\nResearcher: press SPACE to exit.",
    color="white",
    height=0.04,
    wrapWidth=1.25,
    pos=(0, 0),
    alignText="center"
)

# -------------------------
# Instruction screen
# -------------------------

draw_text_and_wait(win, instructions)

# -------------------------
# Start meditation block
# -------------------------

rows = []
event_index = 0
response_count = 0
last_response_task_time = -999
escaped = False

event.clearEvents(eventType="keyboard")

task_clock = core.Clock()
task_start_iso = datetime.now().isoformat()
task_start_unix_sec = time.time()

event_index += 1
rows.append(make_event_row(
    file_stem=file_stem,
    participant_number=participant_number,
    visit=visit,
    block=block,
    date_yyyymmdd=date_yyyymmdd,
    event_index=event_index,
    event_type="task_start",
    trigger_code=TRIGGERS["task_start"],
    task_clock=task_clock,
    response_count=0,
    task_start_iso=task_start_iso,
    task_start_unix_sec=round(task_start_unix_sec, 6),
))
send_trigger(TRIGGERS["task_start"])

# CHANGED: Draw the crosshairs component to screen rather than text warning
fixation.draw()
win.flip()

while task_clock.getTime() < TASK_DURATION_SEC:
    keys = event.getKeys(keyList=[RESPONSE_KEY, QUIT_KEY], timeStamped=task_clock)

    if keys:
        for key, key_task_time in keys:
            if key == QUIT_KEY:
                escaped = True
                break

            if key == RESPONSE_KEY:
                # If the response pad briefly repeats the same key press, do not double count it.
                if (key_task_time - last_response_task_time) >= DEBOUNCE_SEC:
                    last_response_task_time = key_task_time
                    response_count += 1
                    event_index += 1

                    rows.append(make_event_row(
                        file_stem=file_stem,
                        participant_number=participant_number,
                        visit=visit,
                        block=block,
                        date_yyyymmdd=date_yyyymmdd,
                        event_index=event_index,
                        event_type="mind_wandering_button",
                        trigger_code=TRIGGERS["mind_wandering_button"],
                        task_clock=task_clock,
                        response_count=response_count,
                        response_key=key,
                        response_task_time=key_task_time,
                        task_start_iso=task_start_iso,
                        task_start_unix_sec=round(task_start_unix_sec, 6),
                    ))
                    send_trigger(TRIGGERS["mind_wandering_button"])

    if escaped:
        break

    core.wait(0.005)

task_end_iso = datetime.now().isoformat()
task_end_unix_sec = time.time()
actual_duration_sec = task_clock.getTime()
completed = int((not escaped) and actual_duration_sec >= TASK_DURATION_SEC)

event_index += 1
rows.append(make_event_row(
    file_stem=file_stem,
    participant_number=participant_number,
    visit=visit,
    block=block,
    date_yyyymmdd=date_yyyymmdd,
    event_index=event_index,
    event_type="task_end",
    trigger_code=TRIGGERS["task_end"],
    task_clock=task_clock,
    response_count=response_count,
    task_start_iso=task_start_iso,
    task_start_unix_sec=round(task_start_unix_sec, 6),
    task_end_iso=task_end_iso,
    task_end_unix_sec=round(task_end_unix_sec, 6),
    actual_duration_sec=round(actual_duration_sec, 3),
    completed=completed,
    escaped=int(escaped),
))
send_trigger(TRIGGERS["task_end"])

# Fill final task-level values into all rows for easier downstream analysis.
for row in rows:
    row["task_end_iso"] = task_end_iso
    row["task_end_unix_sec"] = round(task_end_unix_sec, 6)
    row["actual_duration_sec"] = round(actual_duration_sec, 3)
    row["completed"] = completed
    row["escaped"] = int(escaped)

# -------------------------
# Save event-level task log
# -------------------------

fieldnames = [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "meditation_type", "event_index", "event_type", "response_count",
    "response_key", "trigger_code", "task_time_sec", "psychopy_global_clock_sec",
    "iso_time", "unix_time_sec", "task_start_iso", "task_start_unix_sec",
    "task_end_iso", "task_end_unix_sec", "planned_duration_sec", "actual_duration_sec",
    "completed", "escaped"
]

with open(output_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

# -------------------------
# End task
# -------------------------

if not escaped:
    end_text.draw()
    win.flip()
    wait_for_researcher_space_or_escape()

win.close()
core.quit()
