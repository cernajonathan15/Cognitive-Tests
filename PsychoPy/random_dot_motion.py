from psychopy import visual, core, event, gui
from datetime import datetime
import time
import csv
import os
import re
import random
import ctypes

# ============================================================
# RANDOM DOT MOTION TASK
# 30-second adaptive practice, optional practice repeats, + 5-minute adaptive four-direction motion coherence task
#
# Response mapping:
#   1 = blue button   -> blue-direction response
#   2 = yellow button -> yellow-direction response
#   3 = green button  -> green-direction response
#   4 = red button    -> red-direction response
#
# Internal direction mapping:
#   blue   = left motion
#   yellow = down motion
#   green  = up motion
#   red    = right motion
#
# Participant-facing instructions use color labels only.
#
# The dot stimulus remains on screen until the participant responds
# or until the active phase window ends.
#
# Adapted from Francesco Cabiddu
# @ https://gitlab.pavlovia.org/Francesco_Cabiddu/staircaserdk/-/blob/master/staircaseRDK-legacy-browsers.js?ref_type=heads
# ============================================================

# -------------------------
# Settings
# -------------------------

TASK_NAME = "random_dot_motion"
TASK_DURATION_SEC = 5 * 60  # 5-minute main task
FULLSCREEN = True
SCREEN_INDEX = 0  # Change to 1 if the stimulus window opens on the wrong monitor.

# Practice settings
# Practice starts a little easier than the main task, then uses the same adaptive
# staircase settings as the main task: MIN_COHERENCE, MAX_COHERENCE,
# STEP_SIZES, and N_UP. There is no trial cap; each practice round runs for the full 30 sec.
# Researchers can repeat practice with R up to MAX_PRACTICE_REPEATS times.
PRACTICE_DURATION_SEC = 30
PRACTICE_START_COHERENCE = 0.70
PRACTICE_FEEDBACK_SEC = 0.60
REPEAT_PRACTICE_KEY = "r"
MAX_PRACTICE_REPEATS = 3

# Response mapping
# Participant-facing labels should use color names only.
BLUE_KEY = "1"    # blue button; internally maps to leftward motion
YELLOW_KEY = "2"  # yellow button; internally maps to downward motion
GREEN_KEY = "3"   # green button; internally maps to upward motion
RED_KEY = "4"     # red button; internally maps to rightward motion
RESPONSE_KEYS = [BLUE_KEY, YELLOW_KEY, GREEN_KEY, RED_KEY]
QUIT_KEY = "escape"

# Dot-stimulus settings
N_DOTS = 200
DOT_SIZE = 8  # DotStim dotSize is best treated as pixels; 0.008 can be effectively invisible.
DOT_SPEED = 0.012
DOT_LIFE_FRAMES = 12
FIELD_SIZE = 0.80
FIELD_SHAPE = "circle"
BLUE_DIR_DEG = 180     # internally: leftward motion
YELLOW_DIR_DEG = 270   # internally: downward motion
GREEN_DIR_DEG = 90     # internally: upward motion
RED_DIR_DEG = 0        # internally: rightward motion

# Short blank interval between trials
INTER_TRIAL_INTERVAL_SEC = 0.30

# Adaptive staircase settings for the main task and adaptive practice.
# This follows the useful idea from the uploaded PsychoJS example,
# but is implemented in Python/PsychoPy and time-limited rather than trial-limited.
START_COHERENCE = 0.50
MIN_COHERENCE = 0.03
MAX_COHERENCE = 0.90
STEP_SIZES = [0.15, 0.10, 0.05, 0.025]
N_UP = 3  # after 3 consecutive correct responses, decrease coherence

# EEG trigger codes
# Practice triggers are intentionally distinct from main-task triggers.
# Edit these if you want to match a different trigger codebook.
TRIGGERS = {
    # Practice phase
    "practice_start": 651,
    "practice_trial_blue_motion_onset": 661,
    "practice_trial_yellow_motion_onset": 662,
    "practice_trial_green_motion_onset": 663,
    "practice_trial_red_motion_onset": 664,
    "practice_response_blue": 671,
    "practice_response_yellow": 672,
    "practice_response_green": 673,
    "practice_response_red": 674,
    "practice_end": 652,

    # Main task phase
    "task_start": 601,
    "trial_blue_motion_onset": 611,
    "trial_yellow_motion_onset": 612,
    "trial_green_motion_onset": 613,
    "trial_red_motion_onset": 614,
    "response_blue": 621,
    "response_yellow": 622,
    "response_green": 623,
    "response_red": 624,
    "task_end": 602,
}

# -------------------------
# Low-Level Parallel Port Initialization (via ctypes)
# -------------------------
# Same structure as the existing lab tasks.
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

def now_iso():
    return datetime.now().isoformat()


def now_unix():
    return time.time()


def send_trigger(code):
    """
    Sends a 5ms TTL pulse to the physical parallel port pins for EEG marking.
    If the driver is not available, prints a mock trigger for testing.
    """
    if io_driver is not None:
        try:
            io_driver.Out32(PORT_ADDRESS, code)
            core.wait(0.005)
            io_driver.Out32(PORT_ADDRESS, 0)
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
        return "RDM"
    value = re.sub(r"[^A-Za-z0-9_-]", "", value)
    return value or "RDM"


def clean_date(value):
    value = str(value).strip()
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 8 else datetime.now().strftime("%Y%m%d")


def check_escape():
    return QUIT_KEY in event.getKeys(keyList=[QUIT_KEY])


def wait_for_researcher_space_or_escape():
    keys = event.waitKeys(keyList=["space", QUIT_KEY])
    return False if QUIT_KEY in keys else True


def wait_for_researcher_space_repeat_or_escape(repeats_used):
    """
    Waits after a practice block.
    SPACE advances to the main task. R repeats practice if fewer than
    MAX_PRACTICE_REPEATS repeat practice rounds have been used.
    """
    if repeats_used < MAX_PRACTICE_REPEATS:
        keys = event.waitKeys(keyList=["space", REPEAT_PRACTICE_KEY, QUIT_KEY])
    else:
        keys = event.waitKeys(keyList=["space", QUIT_KEY])

    if QUIT_KEY in keys:
        return "escape"
    if REPEAT_PRACTICE_KEY in keys and repeats_used < MAX_PRACTICE_REPEATS:
        return "repeat"
    return "main"


def bounded_wait(duration_sec):
    timer = core.Clock()
    while timer.getTime() < duration_sec:
        if check_escape():
            return False
        core.wait(0.005)
    return True


def add_event(events, file_stem, participant_number, visit, block, date_yyyymmdd,
              phase, event_name, trigger_code, phase_clock, global_clock, extra=None):
    row = {
        "file_stem": file_stem,
        "participant_id": f"MLI{participant_number}",
        "participant_number": participant_number,
        "visit": visit,
        "block": block,
        "date_YYYYMMDD": date_yyyymmdd,
        "task_name": TASK_NAME,
        "phase": phase,
        "event_name": event_name,
        "trigger_code": trigger_code,
        "phase_time_sec": round(phase_clock.getTime(), 6) if phase_clock is not None else "",
        "psychopy_global_clock_sec": round(global_clock.getTime(), 6) if global_clock is not None else "",
        "iso_time": now_iso(),
        "unix_time_sec": round(now_unix(), 6),
    }
    if extra:
        row.update(extra)
    events.append(row)


def response_to_color(key):
    if key == BLUE_KEY:
        return "blue"
    if key == YELLOW_KEY:
        return "yellow"
    if key == GREEN_KEY:
        return "green"
    if key == RED_KEY:
        return "red"
    return ""


def color_to_degrees(color):
    if color == "blue":
        return BLUE_DIR_DEG
    if color == "yellow":
        return YELLOW_DIR_DEG
    if color == "green":
        return GREEN_DIR_DEG
    if color == "red":
        return RED_DIR_DEG
    return RED_DIR_DEG


def color_to_key(color):
    if color == "blue":
        return BLUE_KEY
    if color == "yellow":
        return YELLOW_KEY
    if color == "green":
        return GREEN_KEY
    if color == "red":
        return RED_KEY
    return ""


def motion_trigger_name(phase, color):
    if phase == "practice":
        return f"practice_trial_{color}_motion_onset"
    return f"trial_{color}_motion_onset"


def response_trigger_name(phase, color):
    if phase == "practice":
        return f"practice_response_{color}"
    return f"response_{color}"


def run_rdm_trial(win, dots, phase, trial_num, correct_color, coherence,
                  phase_clock, phase_duration_sec, global_clock,
                  file_stem, participant_number, visit, block, date_yyyymmdd,
                  event_rows, practice_round=""):
    """
    Runs one response-terminated RDM trial.
    The dots remain visible until a response is made or the active phase duration ends.
    """
    correct_key = color_to_key(correct_color)
    direction_deg = color_to_degrees(correct_color)
    motion_trigger = TRIGGERS[motion_trigger_name(phase, correct_color)]

    dots.setDir(direction_deg)
    dots.setFieldCoherence(coherence)

    event.clearEvents(eventType="keyboard")
    response_clock = core.Clock()

    # Draw once to establish onset, then mark the first screen flip as trial onset.
    dots.draw()
    win.flip()
    trial_onset_phase_time = phase_clock.getTime()
    trial_onset_global_time = global_clock.getTime()
    trial_onset_iso = now_iso()
    trial_onset_unix = now_unix()
    send_trigger(motion_trigger)
    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        phase, "trial_motion_onset", motion_trigger, phase_clock, global_clock,
        extra={
            "trial_num": trial_num,
            "practice_round": practice_round,
            "correct_color": correct_color,
            "coherence": round(coherence, 6),
        },
    )

    responded = 0
    response_key = ""
    response_color = ""
    response_rt_sec = ""
    response_phase_time = ""
    response_global_time = ""
    response_iso = ""
    response_unix = ""
    response_trigger = ""
    correct = ""
    escaped = False

    while phase_clock.getTime() < phase_duration_sec:
        dots.draw()
        win.flip()

        keys = event.getKeys(keyList=RESPONSE_KEYS + [QUIT_KEY], timeStamped=response_clock)
        if keys:
            for key, rt in keys:
                if key == QUIT_KEY:
                    escaped = True
                    break
                if key in RESPONSE_KEYS:
                    responded = 1
                    response_key = key
                    response_color = response_to_color(key)
                    response_rt_sec = round(rt, 6)
                    response_phase_time = round(phase_clock.getTime(), 6)
                    response_global_time = round(global_clock.getTime(), 6)
                    response_iso = now_iso()
                    response_unix = round(now_unix(), 6)
                    correct = int(response_key == correct_key)
                    response_trigger = TRIGGERS[response_trigger_name(phase, response_color)]
                    send_trigger(response_trigger)
                    add_event(
                        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
                        phase, "response", response_trigger, phase_clock, global_clock,
                        extra={
                            "trial_num": trial_num,
                            "practice_round": practice_round,
                            "response_key": response_key,
                            "response_color": response_color,
                            "response_rt_sec": response_rt_sec,
                            "correct": correct,
                            "coherence": round(coherence, 6),
                        },
                    )
                    break
            if escaped or responded:
                break

        core.wait(0.001)

    trial_offset_phase_time = phase_clock.getTime()
    trial_offset_global_time = global_clock.getTime()
    trial_offset_iso = now_iso()
    trial_offset_unix = now_unix()

    row = {
        "file_stem": file_stem,
        "participant_id": f"MLI{participant_number}",
        "participant_number": participant_number,
        "visit": visit,
        "block": block,
        "date_YYYYMMDD": date_yyyymmdd,
        "task_name": TASK_NAME,
        "phase": phase,
        "practice_round": practice_round,
        "trial_num": trial_num,
        "correct_color": correct_color,
        "correct_key": correct_key,
        "coherence": round(coherence, 6),
        "n_dots": N_DOTS,
        "dot_speed": DOT_SPEED,
        "dot_life_frames": DOT_LIFE_FRAMES,
        "field_size": FIELD_SIZE,
        "trial_onset_phase_time_sec": round(trial_onset_phase_time, 6),
        "trial_onset_global_time_sec": round(trial_onset_global_time, 6),
        "trial_onset_iso": trial_onset_iso,
        "trial_onset_unix_time_sec": round(trial_onset_unix, 6),
        "trial_offset_phase_time_sec": round(trial_offset_phase_time, 6),
        "trial_offset_global_time_sec": round(trial_offset_global_time, 6),
        "trial_offset_iso": trial_offset_iso,
        "trial_offset_unix_time_sec": round(trial_offset_unix, 6),
        "responded": responded,
        "response_key": response_key,
        "response_color": response_color,
        "response_rt_sec": response_rt_sec,
        "response_phase_time_sec": response_phase_time,
        "response_global_time_sec": response_global_time,
        "response_iso": response_iso,
        "response_unix_time_sec": response_unix,
        "correct": correct,
        "motion_onset_trigger": motion_trigger,
        "response_trigger": response_trigger,
    }
    return row, responded, correct, escaped


def show_practice_feedback(win, feedback_stim, correct, responded, remaining_sec):
    if responded:
        feedback_stim.setText("Correct" if correct == 1 else "Incorrect")
    else:
        feedback_stim.setText("No response")

    feedback_stim.draw()
    win.flip()
    return bounded_wait(min(PRACTICE_FEEDBACK_SEC, max(0, remaining_sec)))


def update_staircase(responded, correct, coherence, consecutive_correct,
                     last_staircase_direction, reversal_count, step_position):
    """
    Applies the same 3-up/1-down adaptive staircase to practice and main trials.
    Correct responses count toward making the next trials harder. Incorrect
    responses make the next trial easier. Missed trials at phase end are not
    used to update the staircase.
    """
    staircase_action = "none"

    if responded:
        if correct == 1:
            consecutive_correct += 1
            if consecutive_correct >= N_UP:
                new_direction = "harder"
                coherence = max(MIN_COHERENCE, coherence - STEP_SIZES[step_position])
                staircase_action = "decrease_coherence"
                consecutive_correct = 0

                if last_staircase_direction is not None and last_staircase_direction != new_direction:
                    reversal_count += 1
                    if step_position < len(STEP_SIZES) - 1:
                        step_position += 1

                last_staircase_direction = new_direction
        else:
            new_direction = "easier"
            coherence = min(MAX_COHERENCE, coherence + STEP_SIZES[step_position])
            staircase_action = "increase_coherence"
            consecutive_correct = 0

            if last_staircase_direction is not None and last_staircase_direction != new_direction:
                reversal_count += 1
                if step_position < len(STEP_SIZES) - 1:
                    step_position += 1

            last_staircase_direction = new_direction

    return (
        coherence,
        consecutive_correct,
        last_staircase_direction,
        reversal_count,
        step_position,
        staircase_action,
    )


def safe_float(value):
    try:
        if value == "" or value is None:
            return None
        return float(value)
    except Exception:
        return None


def safe_mean(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 6) if vals else ""


def safe_median(values):
    vals = sorted([v for v in values if v is not None])
    n = len(vals)
    if n == 0:
        return ""
    mid = n // 2
    if n % 2 == 1:
        return round(vals[mid], 6)
    return round((vals[mid - 1] + vals[mid]) / 2, 6)


def safe_proportion(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 6) if vals else ""


def summarize_rows(rows, prefix):
    """
    Creates compact behavioral summary metrics for either practice or main rows.
    The main longitudinal outcomes should generally use the main-task rows only.
    """
    responded = [int(r["responded"]) for r in rows if r.get("responded") != ""]
    correct = [int(r["correct"]) for r in rows if r.get("correct") != ""]
    correct_responded = [int(r["correct"]) for r in rows if r.get("correct") != "" and int(r.get("responded", 0)) == 1]
    coherence_vals = [safe_float(r.get("coherence")) for r in rows]
    rt_vals = [safe_float(r.get("response_rt_sec")) for r in rows if int(r.get("responded", 0)) == 1]
    rt_correct_vals = [safe_float(r.get("response_rt_sec")) for r in rows if int(r.get("responded", 0)) == 1 and r.get("correct") == 1]

    out = {
        f"{prefix}_n_trials": len(rows),
        f"{prefix}_n_responded": sum(responded) if responded else 0,
        f"{prefix}_response_rate": safe_proportion(responded),
        f"{prefix}_accuracy_all_trials": safe_proportion(correct),
        f"{prefix}_accuracy_responded_trials": safe_proportion(correct_responded),
        f"{prefix}_mean_coherence": safe_mean(coherence_vals),
        f"{prefix}_median_coherence": safe_median(coherence_vals),
        f"{prefix}_mean_rt_all_responses_sec": safe_mean(rt_vals),
        f"{prefix}_median_rt_all_responses_sec": safe_median(rt_vals),
        f"{prefix}_mean_rt_correct_sec": safe_mean(rt_correct_vals),
        f"{prefix}_median_rt_correct_sec": safe_median(rt_correct_vals),
    }

    # Per-color outcomes. Useful for catching color-specific mapping problems.
    for color in ["blue", "yellow", "green", "red"]:
        color_rows = [r for r in rows if r.get("correct_color") == color]
        color_correct = [int(r["correct"]) for r in color_rows if r.get("correct") != ""]
        color_rt_correct = [safe_float(r.get("response_rt_sec")) for r in color_rows if int(r.get("responded", 0)) == 1 and r.get("correct") == 1]
        out[f"{prefix}_{color}_n_trials"] = len(color_rows)
        out[f"{prefix}_{color}_accuracy_all_trials"] = safe_proportion(color_correct)
        out[f"{prefix}_{color}_mean_rt_correct_sec"] = safe_mean(color_rt_correct)

    return out


def calculate_outcomes(trial_rows):
    practice_rows = [r for r in trial_rows if r.get("phase") == "practice"]
    main_rows = [r for r in trial_rows if r.get("phase") == "main"]

    outcomes = {}
    outcomes.update(summarize_rows(practice_rows, "practice"))
    outcomes.update(summarize_rows(main_rows, "main"))

    # Final-third coherence metrics for the main task. These are often more informative
    # than full-task coherence because the staircase has had time to settle.
    if main_rows:
        final_third_start = int(len(main_rows) * (2 / 3))
        final_third_rows = main_rows[final_third_start:]
        final_third_coherence = [safe_float(r.get("coherence")) for r in final_third_rows]
        final_third_correct = [int(r["correct"]) for r in final_third_rows if r.get("correct") != ""]
        final_third_rt_correct = [safe_float(r.get("response_rt_sec")) for r in final_third_rows if int(r.get("responded", 0)) == 1 and r.get("correct") == 1]
        outcomes.update({
            "main_final_third_n_trials": len(final_third_rows),
            "main_final_third_mean_coherence": safe_mean(final_third_coherence),
            "main_final_third_median_coherence": safe_median(final_third_coherence),
            "main_final_third_accuracy_all_trials": safe_proportion(final_third_correct),
            "main_final_third_mean_rt_correct_sec": safe_mean(final_third_rt_correct),
            "main_final_third_median_rt_correct_sec": safe_median(final_third_rt_correct),
        })

        # Coherence value at first and last main trial, using coherence used on the trial.
        outcomes["main_first_trial_coherence"] = main_rows[0].get("coherence", "")
        outcomes["main_last_trial_coherence"] = main_rows[-1].get("coherence", "")

        # Accuracy and RT at matched coherence levels. This is stored as compact semicolon-delimited
        # strings so the outcome file remains one row per participant/visit.
        levels = sorted({safe_float(r.get("coherence")) for r in main_rows if safe_float(r.get("coherence")) is not None})
        level_acc_parts = []
        level_rt_parts = []
        level_n_parts = []
        for level in levels:
            level_rows = [r for r in main_rows if safe_float(r.get("coherence")) == level]
            level_correct = [int(r["correct"]) for r in level_rows if r.get("correct") != ""]
            level_rt_correct = [safe_float(r.get("response_rt_sec")) for r in level_rows if int(r.get("responded", 0)) == 1 and r.get("correct") == 1]
            level_n_parts.append(f"{level:.3f}:{len(level_rows)}")
            level_acc_parts.append(f"{level:.3f}:{safe_proportion(level_correct)}")
            level_rt_parts.append(f"{level:.3f}:{safe_mean(level_rt_correct)}")
        outcomes["main_n_by_coherence"] = ";".join(level_n_parts)
        outcomes["main_accuracy_by_coherence"] = ";".join(level_acc_parts)
        outcomes["main_mean_rt_correct_by_coherence_sec"] = ";".join(level_rt_parts)
    else:
        outcomes.update({
            "main_final_third_n_trials": 0,
            "main_final_third_mean_coherence": "",
            "main_final_third_median_coherence": "",
            "main_final_third_accuracy_all_trials": "",
            "main_final_third_mean_rt_correct_sec": "",
            "main_final_third_median_rt_correct_sec": "",
            "main_first_trial_coherence": "",
            "main_last_trial_coherence": "",
            "main_n_by_coherence": "",
            "main_accuracy_by_coherence": "",
            "main_mean_rt_correct_by_coherence_sec": "",
        })

    return outcomes

# -------------------------
# Participant / session dialog
# -------------------------

today_yyyymmdd = datetime.now().strftime("%Y%m%d")

exp_info = {
    "participant_number": "001",
    "visit": "B",
    "block": "RDM",
    "date_YYYYMMDD": today_yyyymmdd,
}

dlg = gui.DlgFromDict(dictionary=exp_info, title="Random Dot Motion Task")
if not dlg.OK:
    core.quit()

participant_number = clean_participant_number(exp_info["participant_number"])
visit = clean_visit(exp_info["visit"])
block = clean_block(exp_info["block"])
date_yyyymmdd = clean_date(exp_info["date_YYYYMMDD"])
file_stem = f"MLI{participant_number}_{visit}_{block}_{date_yyyymmdd}"

output_dir = "data"
os.makedirs(output_dir, exist_ok=True)
trials_file = os.path.join(output_dir, f"{file_stem}_trials.csv")
events_file = os.path.join(output_dir, f"{file_stem}_events.csv")
outcomes_file = os.path.join(output_dir, f"{file_stem}_outcomes.csv")

# -------------------------
# Window and stimuli
# -------------------------

win = visual.Window(size=(1200, 800), fullscr=FULLSCREEN, screen=SCREEN_INDEX, color="black", units="height")

instructions = visual.TextStim(
    win,
    text=(
        "Random Dot Motion Task\n\n"
        "You will see a cloud of moving dots.\n\n"
        "On each trial, press the color button that best matches the overall motion.\n\n"
        "Use only the color buttons:\n"
        "BLUE, YELLOW, GREEN, or RED.\n\n"
        "Please respond as accurately as you can.\n"
        "The dots will stay on the screen until you respond.\n\n"
        "You will first complete a brief practice round with feedback.\n"
        "The practice starts easier and adapts as you respond.\n\n"
        "Researcher: press SPACE to begin the practice."
    ),
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

practice_transition_text = visual.TextStim(
    win,
    text=(
        "Practice complete.\n\n"
        "The real task will begin next.\n\n"
        "Please continue responding as accurately as you can.\n"
        "There will be no feedback during the real task.\n\n"
        "Researcher: press SPACE to begin the 5-minute task, or press R to repeat practice."
    ),
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

practice_repeat_note = visual.TextStim(
    win,
    text="Max of 3 repeat practice trials",
    color="white",
    height=0.022,
    pos=(0, -0.42),
    wrapWidth=1.25,
    italic=True,
)

fixation = visual.TextStim(win, text="+", color="white", height=0.08)
feedback_text = visual.TextStim(win, text="", color="white", height=0.06, wrapWidth=1.25)
end_text = visual.TextStim(
    win,
    text="Random Dot Motion Task Complete\n\nResearcher: press SPACE to exit.",
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

# PsychoPy DotStim handles coherent and noise dots efficiently.
dots = visual.DotStim(
    win=win,
    nDots=N_DOTS,
    coherence=START_COHERENCE,
    fieldPos=(0.0, 0.0),
    fieldSize=FIELD_SIZE,
    fieldShape=FIELD_SHAPE,
    dotSize=DOT_SIZE,
    dotLife=DOT_LIFE_FRAMES,
    dir=RED_DIR_DEG,
    speed=DOT_SPEED,
    color="white",
    signalDots="same",
    noiseDots="direction",
    units="height",
)

# -------------------------
# Instruction screen
# -------------------------

instructions.draw()
win.flip()

if not wait_for_researcher_space_or_escape():
    win.close()
    core.quit()

# -------------------------
# Practice execution
# -------------------------

trial_rows = []
event_rows = []
global_clock = core.Clock()
escaped = False

practice_rounds_completed = 0
practice_repeats_used = 0
total_practice_trials_completed = 0
practice_total_actual_duration_sec = 0.0
practice_start_iso = ""
practice_start_unix_sec = ""
practice_end_iso = ""
practice_end_unix_sec = ""
practice_actual_duration_sec = 0.0
practice_trial_num = 0
practice_final_coherence = PRACTICE_START_COHERENCE
practice_final_reversal_count = 0

while not escaped:
    practice_rounds_completed += 1
    practice_round = practice_rounds_completed
    practice_repeat_index = max(0, practice_round - 1)

    practice_clock = core.Clock()
    this_practice_start_iso = now_iso()
    this_practice_start_unix_sec = now_unix()
    if practice_round == 1:
        practice_start_iso = this_practice_start_iso
        practice_start_unix_sec = this_practice_start_unix_sec

    send_trigger(TRIGGERS["practice_start"])
    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        "practice", "practice_start", TRIGGERS["practice_start"], practice_clock, global_clock,
        extra={
            "practice_round": practice_round,
            "practice_repeat_index": practice_repeat_index,
        },
    )
    event.clearEvents(eventType="keyboard")

    # Keep practice directions roughly balanced while still allowing unlimited trials.
    practice_color_bag = []
    practice_trial_num = 0
    practice_coherence = PRACTICE_START_COHERENCE
    practice_step_position = 0
    practice_consecutive_correct = 0
    practice_last_staircase_direction = None
    practice_reversal_count = 0

    while practice_clock.getTime() < PRACTICE_DURATION_SEC:
        remaining = PRACTICE_DURATION_SEC - practice_clock.getTime()
        if remaining <= 0:
            break

        fixation.draw()
        win.flip()
        if not bounded_wait(min(INTER_TRIAL_INTERVAL_SEC, max(0, remaining))):
            escaped = True
            break

        if practice_clock.getTime() >= PRACTICE_DURATION_SEC:
            break

        practice_trial_num += 1
        if not practice_color_bag:
            practice_color_bag = ["blue", "yellow", "green", "red"]
            random.shuffle(practice_color_bag)
        correct_color = practice_color_bag.pop()
        practice_coherence_before_update = practice_coherence

        row, responded, correct, trial_escaped = run_rdm_trial(
            win, dots, "practice", practice_trial_num, correct_color, practice_coherence,
            practice_clock, PRACTICE_DURATION_SEC, global_clock,
            file_stem, participant_number, visit, block, date_yyyymmdd,
            event_rows, practice_round=practice_round,
        )

        (
            practice_coherence,
            practice_consecutive_correct,
            practice_last_staircase_direction,
            practice_reversal_count,
            practice_step_position,
            practice_staircase_action,
        ) = update_staircase(
            responded, correct, practice_coherence, practice_consecutive_correct,
            practice_last_staircase_direction, practice_reversal_count, practice_step_position
        )

        row.update({
            "practice_round": practice_round,
            "practice_repeat_index": practice_repeat_index,
            "coherence": round(practice_coherence_before_update, 6),
            "coherence_after_update": round(practice_coherence, 6),
            "staircase_action": practice_staircase_action,
            "step_size": STEP_SIZES[practice_step_position],
            "step_position": practice_step_position,
            "consecutive_correct": practice_consecutive_correct,
            "reversal_count": practice_reversal_count,
        })
        trial_rows.append(row)

        if trial_escaped:
            escaped = True
            break

        remaining = PRACTICE_DURATION_SEC - practice_clock.getTime()
        if not show_practice_feedback(win, feedback_text, correct, responded, remaining):
            escaped = True
            break

    this_practice_end_iso = now_iso()
    this_practice_end_unix_sec = now_unix()
    practice_actual_duration_sec = practice_clock.getTime()
    practice_total_actual_duration_sec += practice_actual_duration_sec
    total_practice_trials_completed += practice_trial_num
    practice_end_iso = this_practice_end_iso
    practice_end_unix_sec = this_practice_end_unix_sec
    practice_final_coherence = practice_coherence
    practice_final_reversal_count = practice_reversal_count

    send_trigger(TRIGGERS["practice_end"])
    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        "practice", "practice_end", TRIGGERS["practice_end"], practice_clock, global_clock,
        extra={
            "actual_duration_sec": round(practice_actual_duration_sec, 6),
            "practice_round": practice_round,
            "practice_repeat_index": practice_repeat_index,
            "n_practice_trials_completed": practice_trial_num,
            "practice_final_coherence": round(practice_coherence, 6),
            "practice_reversal_count": practice_reversal_count,
        },
    )

    if escaped:
        break

    # After each practice round, the researcher can either advance to the main task
    # or repeat practice. R is limited to 3 repeat practice rounds.
    if practice_repeats_used < MAX_PRACTICE_REPEATS:
        practice_transition_text.setText(
            "Practice complete.\n\n"
            "The real task will begin next.\n\n"
            "Please continue responding as accurately as you can.\n"
            "There will be no feedback during the real task.\n\n"
            "Researcher: press SPACE to begin the 5-minute task, or press R to repeat practice."
        )
    else:
        practice_transition_text.setText(
            "Practice complete.\n\n"
            "The real task will begin next.\n\n"
            "Please continue responding as accurately as you can.\n"
            "There will be no feedback during the real task.\n\n"
            "Researcher: press SPACE to begin the 5-minute task."
        )

    practice_transition_text.draw()
    practice_repeat_note.draw()
    win.flip()
    transition_choice = wait_for_researcher_space_repeat_or_escape(practice_repeats_used)

    if transition_choice == "escape":
        escaped = True
        break
    if transition_choice == "repeat" and practice_repeats_used < MAX_PRACTICE_REPEATS:
        practice_repeats_used += 1
        continue
    break

# -------------------------
# Main task execution
# -------------------------


coherence = START_COHERENCE
step_position = 0
consecutive_correct = 0
last_staircase_direction = None  # "harder" or "easier"
reversal_count = 0
main_trial_num = 0

if not escaped:
    task_clock = core.Clock()
    task_start_iso = now_iso()
    task_start_unix_sec = now_unix()
    send_trigger(TRIGGERS["task_start"])
    add_event(event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
              "main", "task_start", TRIGGERS["task_start"], task_clock, global_clock)
    event.clearEvents(eventType="keyboard")

    while task_clock.getTime() < TASK_DURATION_SEC:
        remaining = TASK_DURATION_SEC - task_clock.getTime()
        if remaining <= 0:
            break

        # Brief fixation/blank between trials
        fixation.draw()
        win.flip()
        if not bounded_wait(min(INTER_TRIAL_INTERVAL_SEC, max(0, remaining))):
            escaped = True
            break

        if task_clock.getTime() >= TASK_DURATION_SEC:
            break

        main_trial_num += 1
        correct_color = random.choice(["blue", "yellow", "green", "red"])
        coherence_before_update = coherence

        row, responded, correct, trial_escaped = run_rdm_trial(
            win, dots, "main", main_trial_num, correct_color, coherence,
            task_clock, TASK_DURATION_SEC, global_clock,
            file_stem, participant_number, visit, block, date_yyyymmdd,
            event_rows,
        )

        if trial_escaped:
            escaped = True

        # Update staircase after a main-task response, using the same rule as practice.
        (
            coherence,
            consecutive_correct,
            last_staircase_direction,
            reversal_count,
            step_position,
            staircase_action,
        ) = update_staircase(
            responded, correct, coherence, consecutive_correct,
            last_staircase_direction, reversal_count, step_position
        )

        row.update({
            "coherence": round(coherence_before_update, 6),
            "coherence_after_update": round(coherence, 6),
            "staircase_action": staircase_action,
            "step_size": STEP_SIZES[step_position],
            "step_position": step_position,
            "consecutive_correct": consecutive_correct,
            "reversal_count": reversal_count,
        })
        trial_rows.append(row)

        if escaped:
            break

    task_end_iso = now_iso()
    task_end_unix_sec = now_unix()
    actual_duration_sec = task_clock.getTime()
    send_trigger(TRIGGERS["task_end"])
    add_event(event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
              "main", "task_end", TRIGGERS["task_end"], task_clock, global_clock,
              extra={
                  "actual_duration_sec": round(actual_duration_sec, 6),
                  "completed": int((actual_duration_sec >= TASK_DURATION_SEC) and not escaped),
                  "n_trials_completed": main_trial_num,
              })
else:
    # If escape occurred before the main task, preserve blank task timing fields in the summary.
    task_start_iso = ""
    task_start_unix_sec = ""
    task_end_iso = ""
    task_end_unix_sec = ""
    actual_duration_sec = 0

# -------------------------
# Save files
# -------------------------

trial_fieldnames = [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "phase", "practice_round", "practice_repeat_index", "trial_num", "correct_color", "correct_key", "coherence", "n_dots",
    "dot_speed", "dot_life_frames", "field_size", "trial_onset_phase_time_sec",
    "trial_onset_global_time_sec", "trial_onset_iso", "trial_onset_unix_time_sec",
    "trial_offset_phase_time_sec", "trial_offset_global_time_sec", "trial_offset_iso",
    "trial_offset_unix_time_sec", "responded", "response_key", "response_color",
    "response_rt_sec", "response_phase_time_sec", "response_global_time_sec", "response_iso",
    "response_unix_time_sec", "correct", "motion_onset_trigger", "response_trigger",
    "coherence_after_update", "staircase_action", "step_size", "step_position",
    "consecutive_correct", "reversal_count",
]

with open(trials_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=trial_fieldnames)
    writer.writeheader()
    writer.writerows(trial_rows)

event_fieldnames = sorted(set().union(*(row.keys() for row in event_rows))) if event_rows else []
with open(events_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=event_fieldnames)
    writer.writeheader()
    writer.writerows(event_rows)

# Save one-row outcomes file for longitudinal analysis across Baseline, W2, W4, W6, and W8.
outcomes = calculate_outcomes(trial_rows)
outcomes.update({
    "file_stem": file_stem,
    "participant_id": f"MLI{participant_number}",
    "participant_number": participant_number,
    "visit": visit,
    "block": block,
    "date_YYYYMMDD": date_yyyymmdd,
    "task_name": TASK_NAME,
    "main_start_coherence_setting": START_COHERENCE,
    "main_min_coherence_setting": MIN_COHERENCE,
    "main_max_coherence_setting": MAX_COHERENCE,
    "main_step_sizes_setting": ";".join(str(x) for x in STEP_SIZES),
    "main_n_up_setting": N_UP,
    "practice_start_coherence_setting": PRACTICE_START_COHERENCE,
    "practice_adaptive_setting": 1,
    "practice_trial_cap_setting": "none",
    "practice_duration_sec_setting": PRACTICE_DURATION_SEC,
    "practice_max_repeats_setting": MAX_PRACTICE_REPEATS,
    "practice_repeats_used": practice_repeats_used,
    "practice_rounds_completed": practice_rounds_completed,
    "inter_trial_interval_sec_setting": INTER_TRIAL_INTERVAL_SEC,
})

outcome_first_fields = [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "main_start_coherence_setting", "main_min_coherence_setting",
    "main_max_coherence_setting", "main_step_sizes_setting", "main_n_up_setting",
    "practice_start_coherence_setting", "practice_adaptive_setting", "practice_trial_cap_setting",
    "practice_duration_sec_setting", "practice_max_repeats_setting",
    "practice_repeats_used", "practice_rounds_completed",
    "inter_trial_interval_sec_setting",
]
outcome_fieldnames = outcome_first_fields + sorted([k for k in outcomes.keys() if k not in outcome_first_fields])
with open(outcomes_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=outcome_fieldnames)
    writer.writeheader()
    writer.writerow(outcomes)

# Also save a minimal task summary.
summary_file = os.path.join(output_dir, f"{file_stem}_summary.csv")
with open(summary_file, mode="w", newline="", encoding="utf-8") as f:
    fieldnames = [
        "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
        "task_name", "practice_planned_duration_sec", "practice_actual_duration_sec",
        "practice_rounds_completed", "practice_repeats_used",
        "practice_start_iso", "practice_end_iso", "practice_start_unix_sec", "practice_end_unix_sec",
        "n_practice_trials_completed", "practice_final_coherence", "practice_reversal_count",
        "main_planned_duration_sec", "main_actual_duration_sec",
        "main_start_iso", "main_end_iso", "main_start_unix_sec", "main_end_unix_sec",
        "completed", "escaped", "n_main_trials_completed", "final_coherence", "reversal_count",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow({
        "file_stem": file_stem,
        "participant_id": f"MLI{participant_number}",
        "participant_number": participant_number,
        "visit": visit,
        "block": block,
        "date_YYYYMMDD": date_yyyymmdd,
        "task_name": TASK_NAME,
        "practice_planned_duration_sec": PRACTICE_DURATION_SEC,
        "practice_actual_duration_sec": round(practice_total_actual_duration_sec, 6),
        "practice_rounds_completed": practice_rounds_completed,
        "practice_repeats_used": practice_repeats_used,
        "practice_start_iso": practice_start_iso,
        "practice_end_iso": practice_end_iso,
        "practice_start_unix_sec": round(practice_start_unix_sec, 6),
        "practice_end_unix_sec": round(practice_end_unix_sec, 6),
        "n_practice_trials_completed": total_practice_trials_completed,
        "practice_final_coherence": round(practice_final_coherence, 6),
        "practice_reversal_count": practice_final_reversal_count,
        "main_planned_duration_sec": TASK_DURATION_SEC,
        "main_actual_duration_sec": round(actual_duration_sec, 6),
        "main_start_iso": task_start_iso,
        "main_end_iso": task_end_iso,
        "main_start_unix_sec": round(task_start_unix_sec, 6) if task_start_unix_sec != "" else "",
        "main_end_unix_sec": round(task_end_unix_sec, 6) if task_end_unix_sec != "" else "",
        "completed": int((actual_duration_sec >= TASK_DURATION_SEC) and not escaped),
        "escaped": int(escaped),
        "n_main_trials_completed": main_trial_num,
        "final_coherence": round(coherence, 6),
        "reversal_count": reversal_count,
    })

end_text.draw()
win.flip()
wait_for_researcher_space_or_escape()

win.close()
core.quit()
