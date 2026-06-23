from psychopy import visual, core, event, gui, sound
from datetime import datetime
import time
import csv
import os
import re
import random
import ctypes

# ============================================================
# MOTOR CONTROL TASK
# 5-minute auditory control task:
#   Block 1: AuditoryOnly  - hear tones, no button press
#   Block 2: AuditoryMotor - hear tones, press button after each tone
#
# Revised version: adds Unix-time output while preserving the
# original relative/global PsychoPy timing and ISO clock-time output.
# ============================================================

# -------------------------
# Settings
# -------------------------

TASK_NAME = "motor_control"
FULLSCREEN = True

BLOCK_DURATION_SEC = 2.5 * 60  # 150 seconds per block
TOTAL_DURATION_SEC = BLOCK_DURATION_SEC * 2

# Tone settings
TONE_FREQ_HZ = 750
TONE_DURATION_SEC = 0.10  # 100 ms tone
TONE_VOLUME = 0.50

# Timing settings
ITI_RANGE_SEC = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)

# Hardware Response Mapping (Left = "1", Right = "4")
RESPONSE_KEYS = ["1", "4"]
RESPONSE_WINDOW_SEC = 1.5
POST_TONE_PERIOD_SEC = 1.5

QUIT_KEY = "escape"
SHOW_FIXATION = True
FIXATION_TEXT = "+"

# EEG Trigger Codes
TRIGGERS = {
    "AuditoryOnly_start": 201,
    "AuditoryOnly_tone": 211,
    "AuditoryOnly_end": 202,
    "AuditoryMotor_start": 301,
    "AuditoryMotor_tone": 311,
    "AuditoryMotor_response": 312,
    "AuditoryMotor_end": 302,
}

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

def now_iso_unix():
    """
    Returns local clock time as ISO string and Unix epoch time in seconds.
    Called as close as possible to each logged event.
    """
    return datetime.now().isoformat(), time.time()


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
        return "MotorControl"
    value = re.sub(r"[^A-Za-z0-9_-]", "", value)
    return value or "MotorControl"


def clean_date(value):
    value = str(value).strip()
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 8 else datetime.now().strftime("%Y%m%d")


def check_escape():
    return QUIT_KEY in event.getKeys(keyList=[QUIT_KEY])


def wait_for_researcher_space_or_escape():
    keys = event.waitKeys(keyList=["space", QUIT_KEY])
    return False if QUIT_KEY in keys else True


def draw_text_and_wait(win, text_stim):
    text_stim.draw()
    win.flip()
    if not wait_for_researcher_space_or_escape():
        win.close()
        core.quit()


def bounded_wait(duration_sec):
    timer = core.Clock()
    while timer.getTime() < duration_sec:
        if check_escape():
            return False
        core.wait(0.005)
    return True


def finalize_block_rows(rows, block_end_iso, block_end_unix_sec, block_completed):
    """
    Adds block-level end timing to every event row from the block.
    """
    for row in rows:
        row["block_end_iso"] = block_end_iso
        row["block_end_unix_sec"] = round(block_end_unix_sec, 6)
        row["block_completed"] = int(block_completed)
    return rows


def run_block(
    win,
    tone_stim,
    fixation,
    block_name,
    requires_response,
    block_duration_sec,
    global_clock,
    file_stem,
    participant_number,
    visit,
    date_yyyymmdd,
):
    rows = []
    block_clock = core.Clock()
    trial_num = 0

    block_start_iso, block_start_unix_sec = now_iso_unix()
    block_start_global_time = global_clock.getTime()

    send_trigger(TRIGGERS[f"{block_name}_start"])
    event.clearEvents(eventType="keyboard")

    while block_clock.getTime() < block_duration_sec:
        iti_sec = random.choice(ITI_RANGE_SEC)
        remaining_before_iti = block_duration_sec - block_clock.getTime()
        if remaining_before_iti <= 0:
            break

        actual_iti = min(iti_sec, remaining_before_iti)
        if SHOW_FIXATION:
            fixation.draw()
        win.flip()

        if not bounded_wait(actual_iti):
            block_end_iso, block_end_unix_sec = now_iso_unix()
            send_trigger(TRIGGERS[f"{block_name}_end"])
            return (
                finalize_block_rows(rows, block_end_iso, block_end_unix_sec, False),
                False,
                block_start_iso,
                block_end_iso,
                block_start_unix_sec,
                block_end_unix_sec,
            )

        if (block_duration_sec - block_clock.getTime()) < TONE_DURATION_SEC:
            break

        trial_num += 1
        event.clearEvents(eventType="keyboard")

        tone_onset_block_time = block_clock.getTime()
        tone_onset_global_time = global_clock.getTime()
        tone_onset_iso, tone_onset_unix_sec = now_iso_unix()

        send_trigger(TRIGGERS[f"{block_name}_tone"])
        tone_stim.play()

        if SHOW_FIXATION:
            fixation.draw()
        win.flip()

        if not bounded_wait(TONE_DURATION_SEC):
            block_end_iso, block_end_unix_sec = now_iso_unix()
            send_trigger(TRIGGERS[f"{block_name}_end"])
            return (
                finalize_block_rows(rows, block_end_iso, block_end_unix_sec, False),
                False,
                block_start_iso,
                block_end_iso,
                block_start_unix_sec,
                block_end_unix_sec,
            )

        tone_offset_block_time = block_clock.getTime()
        tone_offset_global_time = global_clock.getTime()
        tone_offset_iso, tone_offset_unix_sec = now_iso_unix()

        response_key = ""
        response_rt_sec = ""
        response_global_time = ""
        response_iso = ""
        response_unix_sec = ""
        responded = 0
        correct_response = ""
        accidental_response = 0
        missed_response = 0

        response_clock = core.Clock()
        collection_window = min(POST_TONE_PERIOD_SEC, max(0, block_duration_sec - block_clock.getTime()))

        while response_clock.getTime() < collection_window:
            keys = event.getKeys(keyList=RESPONSE_KEYS + [QUIT_KEY], timeStamped=response_clock)
            if keys:
                for key, rt in keys:
                    if key == QUIT_KEY:
                        block_end_iso, block_end_unix_sec = now_iso_unix()
                        send_trigger(TRIGGERS[f"{block_name}_end"])
                        return (
                            finalize_block_rows(rows, block_end_iso, block_end_unix_sec, False),
                            False,
                            block_start_iso,
                            block_end_iso,
                            block_start_unix_sec,
                            block_end_unix_sec,
                        )

                    if key in RESPONSE_KEYS and not responded:
                        responded = 1
                        response_key = key
                        response_rt_sec = round(rt, 6)
                        response_global_time = round(global_clock.getTime(), 6)
                        response_iso, response_unix_sec = now_iso_unix()
                        response_unix_sec = round(response_unix_sec, 6)

                        if requires_response:
                            correct_response = 1
                            send_trigger(TRIGGERS["AuditoryMotor_response"])
                        else:
                            correct_response = 0
                            accidental_response = 1
            core.wait(0.001)

        if requires_response and not responded:
            correct_response = 0
            missed_response = 1
        if not requires_response and not responded:
            correct_response = ""
            accidental_response = 0
            missed_response = ""

        rows.append({
            "file_stem": file_stem,
            "participant_id": f"MLI{participant_number}",
            "participant_number": participant_number,
            "visit": visit,
            "date_YYYYMMDD": date_yyyymmdd,
            "task_name": TASK_NAME,
            "block_name": block_name,
            "requires_response": int(requires_response),
            "trial_num": trial_num,
            "iti_sec": round(actual_iti, 6),
            "tone_frequency_hz": TONE_FREQ_HZ,
            "tone_duration_sec": TONE_DURATION_SEC,
            "tone_volume": TONE_VOLUME,
            "post_tone_period_sec": POST_TONE_PERIOD_SEC,
            "tone_onset_block_time_sec": round(tone_onset_block_time, 6),
            "tone_onset_global_time_sec": round(tone_onset_global_time, 6),
            "tone_onset_iso": tone_onset_iso,
            "tone_onset_unix_sec": round(tone_onset_unix_sec, 6),
            "tone_offset_block_time_sec": round(tone_offset_block_time, 6),
            "tone_offset_global_time_sec": round(tone_offset_global_time, 6),
            "tone_offset_iso": tone_offset_iso,
            "tone_offset_unix_sec": round(tone_offset_unix_sec, 6),
            "response_key": response_key,
            "response_rt_sec": response_rt_sec,
            "response_global_time_sec": response_global_time,
            "response_iso": response_iso,
            "response_unix_sec": response_unix_sec,
            "responded": responded,
            "correct_response": correct_response,
            "missed_response": missed_response,
            "accidental_response": accidental_response,
            "block_start_iso": block_start_iso,
            "block_start_unix_sec": round(block_start_unix_sec, 6),
            "block_start_global_time_sec": round(block_start_global_time, 6),
            "block_planned_duration_sec": block_duration_sec,
        })

    block_end_iso, block_end_unix_sec = now_iso_unix()
    send_trigger(TRIGGERS[f"{block_name}_end"])
    return (
        finalize_block_rows(rows, block_end_iso, block_end_unix_sec, True),
        True,
        block_start_iso,
        block_end_iso,
        block_start_unix_sec,
        block_end_unix_sec,
    )

# -------------------------
# Run Initialization & Windows Setup
# -------------------------

today_yyyymmdd = datetime.now().strftime("%Y%m%d")
exp_info = {
    "participant_number": "001",
    "visit": "B",
    "block": "MotorControl",
    "date_YYYYMMDD": today_yyyymmdd,
}

dlg = gui.DlgFromDict(dictionary=exp_info, title="Motor Control Task")
if not dlg.OK:
    core.quit()

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
# Stimuli Definition
# -------------------------

instructions_intro = visual.TextStim(
    win,
    text=(
        "Motor Control Task\n\n"
        "This task has two short blocks.\n\n"
        "Block 1: You will hear tones. Please do NOT press the button.\n\n"
        "Block 2: You will hear the same tones. Please press the button once after each tone.\n\n"
        "Please remain still, relaxed, and keep your eyes closed during each block.\n\n"
        "Researcher: press SPACE to continue."
    ),
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

instructions_auditory_only = visual.TextStim(
    win,
    text=(
        "Block 1: Auditory Only\n\n"
        "You will hear a series of tones.\n\n"
        "Please keep your eyes closed and do NOT press the button during this block.\n\n"
        "Researcher: press SPACE to begin the 2.5-minute block."
    ),
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

instructions_auditory_motor = visual.TextStim(
    win,
    text=(
        "Block 2: Auditory + Motor\n\n"
        "You will hear the same series of tones.\n\n"
        "Please keep your eyes closed and press the button once after each tone.\n\n"
        "Researcher: press SPACE to begin the 2.5-minute block."
    ),
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

transition_text = visual.TextStim(
    win,
    text="The first block is complete.\n\nResearcher: press SPACE to continue to the second block.",
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

end_text = visual.TextStim(
    win,
    text="Motor Control Task Complete\n\nResearcher: press SPACE to exit.",
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

fixation = visual.TextStim(win, text=FIXATION_TEXT, color="white", height=0.08)

# REVISED SOUND SETUP: Bypasses explicit hardware profile routing to target active Windows device.
tone_stim = sound.Sound(value=TONE_FREQ_HZ, secs=TONE_DURATION_SEC, sampleRate=44100, volume=TONE_VOLUME, stereo=True, hamming=True)

# -------------------------
# Task Execution Loop
# -------------------------

all_rows = []
task_start_iso, task_start_unix_sec = now_iso_unix()
global_clock = core.Clock()
escaped = False

draw_text_and_wait(win, instructions_intro)
draw_text_and_wait(win, instructions_auditory_only)

auditory_only_rows, completed_auditory_only, ao_start, ao_end, ao_start_unix, ao_end_unix = run_block(
    win,
    tone_stim,
    fixation,
    "AuditoryOnly",
    False,
    BLOCK_DURATION_SEC,
    global_clock,
    file_stem,
    participant_number,
    visit,
    date_yyyymmdd,
)
all_rows.extend(auditory_only_rows)
if not completed_auditory_only:
    escaped = True

if not escaped:
    draw_text_and_wait(win, transition_text)
    draw_text_and_wait(win, instructions_auditory_motor)
    auditory_motor_rows, completed_auditory_motor, am_start, am_end, am_start_unix, am_end_unix = run_block(
        win,
        tone_stim,
        fixation,
        "AuditoryMotor",
        True,
        BLOCK_DURATION_SEC,
        global_clock,
        file_stem,
        participant_number,
        visit,
        date_yyyymmdd,
    )
    all_rows.extend(auditory_motor_rows)
    if not completed_auditory_motor:
        escaped = True

task_end_iso, task_end_unix_sec = now_iso_unix()
actual_duration_sec = global_clock.getTime()

# -------------------------
# Data Logging
# -------------------------

fieldnames = [
    "file_stem",
    "participant_id",
    "participant_number",
    "visit",
    "date_YYYYMMDD",
    "task_name",
    "block_name",
    "requires_response",
    "trial_num",
    "iti_sec",
    "tone_frequency_hz",
    "tone_duration_sec",
    "tone_volume",
    "post_tone_period_sec",
    "tone_onset_block_time_sec",
    "tone_onset_global_time_sec",
    "tone_onset_iso",
    "tone_onset_unix_sec",
    "tone_offset_block_time_sec",
    "tone_offset_global_time_sec",
    "tone_offset_iso",
    "tone_offset_unix_sec",
    "response_key",
    "response_rt_sec",
    "response_global_time_sec",
    "response_iso",
    "response_unix_sec",
    "responded",
    "correct_response",
    "missed_response",
    "accidental_response",
    "block_start_iso",
    "block_start_unix_sec",
    "block_start_global_time_sec",
    "block_end_iso",
    "block_end_unix_sec",
    "block_planned_duration_sec",
    "block_completed",
    "task_start_iso",
    "task_start_unix_sec",
    "task_end_iso",
    "task_end_unix_sec",
    "planned_total_duration_sec",
    "actual_total_duration_sec",
    "completed",
    "escaped",
]

with open(output_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in all_rows:
        row["task_start_iso"] = task_start_iso
        row["task_start_unix_sec"] = round(task_start_unix_sec, 6)
        row["task_end_iso"] = task_end_iso
        row["task_end_unix_sec"] = round(task_end_unix_sec, 6)
        row["planned_total_duration_sec"] = TOTAL_DURATION_SEC
        row["actual_total_duration_sec"] = round(actual_duration_sec, 3)
        row["completed"] = int((not escaped) and actual_duration_sec >= TOTAL_DURATION_SEC)
        row["escaped"] = int(escaped)
        writer.writerow(row)

if not escaped:
    end_text.draw()
    win.flip()
    wait_for_researcher_space_or_escape()

win.close()
core.quit()