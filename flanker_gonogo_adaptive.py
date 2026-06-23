from psychopy import visual, core, event, gui
from psychopy.hardware import keyboard
from datetime import datetime
import time
import csv
import os
import re
import random
import statistics
import ctypes

# ============================================================
# ADAPTIVE FLANKER GO/NO-GO TASK
# 45-second adaptive practice, optional practice repeats, + 5-minute adaptive main task
#
# Response mapping:
#   1 = blue/left response-pad button  -> center arrow points left
#   4 = red/right response-pad button  -> center arrow points right
#
# Trial logic:
#   GO trials:   center arrow points left or right in white.
#                Press the matching left/right button as quickly and accurately as possible.
#   NO-GO trials: center arrow is RED. Do not press anything, even though the
#                arrow still points left or right and flankers may create conflict.
#
# Adaptive logic:
#   Difficulty changes after short performance windows. Unlike the RDM task,
#   difficulty is NOT coherence-based. It changes stimulus duration, response
#   window, no-go probability, incongruent proportion, and ISI.
#
# EEG / CURRY note:
#   Trigger values are intentionally kept within 1-255 so that an 8-bit trigger
#   receiver does not wrap values such as 401 or 601 into unexpected values.
# ============================================================

# -------------------------
# Settings
# -------------------------

TASK_NAME = "flanker_gonogo"
TASK_DURATION_SEC = 5 * 60
FULLSCREEN = True
SCREEN_INDEX = 0  # Change to 1 if the stimulus window opens on the wrong monitor.

# Practice settings
PRACTICE_DURATION_SEC = 45
PRACTICE_FEEDBACK_SEC = 0.45
REPEAT_PRACTICE_KEY = "r"
MAX_PRACTICE_REPEATS = 3

# Timing
INITIAL_START_DELAY_SEC = 1.000
MIN_REMAINING_TO_START_TRIAL_SEC = 0.35
# Adaptation is checked often, but each decision uses a rolling performance window.
# Main task: check every 10 trials using the most recent 20 trials.
# Practice: check every 8 trials using the most recent 16 trials because feedback slows practice.
ADAPT_CHECK_INTERVAL_N_TRIALS = 10
ADAPT_WINDOW_N_TRIALS = 20
PRACTICE_ADAPT_CHECK_INTERVAL_N_TRIALS = 8
PRACTICE_ADAPT_WINDOW_N_TRIALS = 16

# Response mapping
LEFT_KEYS = ["1", "num_1"]
RIGHT_KEYS = ["4", "num_4"]
RESPONSE_KEYS = LEFT_KEYS + RIGHT_KEYS
QUIT_KEY = "escape"

# Display colors. Red is the only task-relevant color cue and means No-Go.
GO_TARGET_COLOR = "white"
NOGO_TARGET_COLOR = "red"
FLANKER_COLOR = "white"
FIXATION_COLOR = "white"
BACKGROUND_COLOR = "black"

# Stimulus geometry
ARROW_HEIGHT = 0.14
ARROW_X_POSITIONS = [-0.28, -0.14, 0.0, 0.14, 0.28]
STIM_Y = 0.02

# Adaptive difficulty levels.
# Higher levels are harder: shorter exposure, shorter response window,
# rarer no-go trials that increase Go-response prepotency, more incongruent
# trials, and shorter ISIs.
DIFFICULTY_LEVELS = [
    # Easier levels have more No-Go trials. Harder levels make Go responses more
    # prepotent by making No-Go trials rarer while increasing speed and conflict.
    {"level": 1, "stim_duration_sec": 0.150, "response_window_sec": 1.100, "isi_options_sec": [0.900, 1.050, 1.200], "nogo_prob": 0.25, "go_incongruent_prob": 0.35, "nogo_incongruent_prob": 0.35},
    {"level": 2, "stim_duration_sec": 0.133, "response_window_sec": 1.050, "isi_options_sec": [0.800, 0.950, 1.100], "nogo_prob": 0.22, "go_incongruent_prob": 0.40, "nogo_incongruent_prob": 0.40},
    {"level": 3, "stim_duration_sec": 0.100, "response_window_sec": 1.000, "isi_options_sec": [0.700, 0.850, 1.000], "nogo_prob": 0.20, "go_incongruent_prob": 0.45, "nogo_incongruent_prob": 0.45},
    {"level": 4, "stim_duration_sec": 0.083, "response_window_sec": 0.900, "isi_options_sec": [0.550, 0.700, 0.850], "nogo_prob": 0.18, "go_incongruent_prob": 0.50, "nogo_incongruent_prob": 0.50},
    {"level": 5, "stim_duration_sec": 0.083, "response_window_sec": 0.850, "isi_options_sec": [0.500, 0.625, 0.750], "nogo_prob": 0.16, "go_incongruent_prob": 0.55, "nogo_incongruent_prob": 0.55},
    {"level": 6, "stim_duration_sec": 0.067, "response_window_sec": 0.800, "isi_options_sec": [0.450, 0.575, 0.700], "nogo_prob": 0.14, "go_incongruent_prob": 0.60, "nogo_incongruent_prob": 0.60},
    {"level": 7, "stim_duration_sec": 0.067, "response_window_sec": 0.750, "isi_options_sec": [0.400, 0.525, 0.650], "nogo_prob": 0.12, "go_incongruent_prob": 0.65, "nogo_incongruent_prob": 0.65},
    {"level": 8, "stim_duration_sec": 0.050, "response_window_sec": 0.700, "isi_options_sec": [0.350, 0.475, 0.600], "nogo_prob": 0.10, "go_incongruent_prob": 0.70, "nogo_incongruent_prob": 0.70},
    {"level": 9, "stim_duration_sec": 0.050, "response_window_sec": 0.650, "isi_options_sec": [0.300, 0.425, 0.550], "nogo_prob": 0.10, "go_incongruent_prob": 0.75, "nogo_incongruent_prob": 0.75},
]
START_DIFFICULTY_LEVEL = 4
PRACTICE_START_DIFFICULTY_LEVEL = 2

# Adaptive decision thresholds.
# These are intentionally demanding so that the task can move upward only when
# participants are doing well on both go and no-go components.
HARDER_GO_ACCURACY = 0.85
HARDER_NOGO_FALSE_ALARM = 0.20
HARDER_MEAN_GO_RT_SEC = 0.650
HARDER_GO_OMISSION = 0.15
EASIER_GO_ACCURACY = 0.70
EASIER_NOGO_FALSE_ALARM = 0.45
EASIER_GO_OMISSION = 0.25

# EEG trigger codes, all <=255.
# Main and practice triggers are distinct.
TRIGGERS = {
    # Main task
    "task_start": 101,
    "go_congruent_left_onset": 111,
    "go_congruent_right_onset": 112,
    "go_incongruent_left_onset": 113,
    "go_incongruent_right_onset": 114,
    "nogo_congruent_left_onset": 115,
    "nogo_congruent_right_onset": 116,
    "nogo_incongruent_left_onset": 117,
    "nogo_incongruent_right_onset": 118,
    "response_left": 121,
    "response_right": 122,
    "task_end": 102,

    # Practice
    "practice_start": 141,
    "practice_go_congruent_left_onset": 151,
    "practice_go_congruent_right_onset": 152,
    "practice_go_incongruent_left_onset": 153,
    "practice_go_incongruent_right_onset": 154,
    "practice_nogo_congruent_left_onset": 155,
    "practice_nogo_congruent_right_onset": 156,
    "practice_nogo_incongruent_left_onset": 157,
    "practice_nogo_incongruent_right_onset": 158,
    "practice_response_left": 161,
    "practice_response_right": 162,
    "practice_end": 142,
}

# -------------------------
# Low-Level Parallel Port Initialization (via ctypes)
# -------------------------
# Same structure as the existing lab tasks.
DLL_DIR = r"C:\Users\mindlab\Documents\PsychoPy\Test Tasks\IO"
dll_64_path = os.path.join(DLL_DIR, "inpoutx64.dll")

io_driver = None
PORT_ADDRESS = 0x3FF8  # Verified hardware port address in prior task files.

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
    If the driver is unavailable, prints a mock trigger for testing.
    """
    code = int(code)
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
        return "FGNG"
    value = re.sub(r"[^A-Za-z0-9_-]", "", value)
    return value or "FGNG"


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


def key_to_response(key_name):
    if key_name in LEFT_KEYS:
        return "left"
    if key_name in RIGHT_KEYS:
        return "right"
    return ""


def response_trigger_name(phase, response_side):
    prefix = "practice_" if phase == "practice" else ""
    return f"{prefix}response_{response_side}"


def onset_trigger_name(phase, trial_type, congruency, target_direction):
    prefix = "practice_" if phase == "practice" else ""
    return f"{prefix}{trial_type}_{congruency}_{target_direction}_onset"


def get_level_settings(level):
    level = max(1, min(int(level), len(DIFFICULTY_LEVELS)))
    return DIFFICULTY_LEVELS[level - 1].copy()


def balanced_directions(n):
    directions = []
    for _ in range(n // 2):
        directions.extend(["left", "right"])
    if n % 2:
        directions.append(random.choice(["left", "right"]))
    random.shuffle(directions)
    return directions


def add_trials_to_bag(bag, n, trial_type, congruency):
    for direction in balanced_directions(n):
        bag.append({
            "trial_type": trial_type,
            "congruency": congruency,
            "target_direction": direction,
        })


def build_trial_bag(level, bag_size=ADAPT_WINDOW_N_TRIALS):
    """
    Builds a short trial bag using the current adaptive level. The bag preserves
    approximate control-load proportions while keeping left/right directions balanced.
    """
    settings = get_level_settings(level)

    n_nogo = int(round(bag_size * settings["nogo_prob"]))
    n_nogo = max(2, min(bag_size - 4, n_nogo))
    n_go = bag_size - n_nogo

    n_go_incongruent = int(round(n_go * settings["go_incongruent_prob"]))
    n_go_incongruent = max(1, min(n_go - 1, n_go_incongruent))
    n_go_congruent = n_go - n_go_incongruent

    n_nogo_incongruent = int(round(n_nogo * settings["nogo_incongruent_prob"]))
    n_nogo_incongruent = max(1, min(n_nogo - 1, n_nogo_incongruent))
    n_nogo_congruent = n_nogo - n_nogo_incongruent

    bag = []
    add_trials_to_bag(bag, n_go_congruent, "go", "congruent")
    add_trials_to_bag(bag, n_go_incongruent, "go", "incongruent")
    add_trials_to_bag(bag, n_nogo_congruent, "nogo", "congruent")
    add_trials_to_bag(bag, n_nogo_incongruent, "nogo", "incongruent")

    random.shuffle(bag)
    return bag


def mean_or_blank(values):
    vals = [v for v in values if v is not None and v != ""]
    if not vals:
        return ""
    return round(sum(vals) / len(vals), 6)


def sd_or_blank(values):
    vals = [v for v in values if v is not None and v != ""]
    if len(vals) < 2:
        return ""
    return round(statistics.stdev(vals), 6)


def proportion_or_blank(values):
    vals = [v for v in values if v is not None and v != ""]
    if not vals:
        return ""
    return round(sum(vals) / len(vals), 6)


def evaluate_performance(rows):
    go_rows = [r for r in rows if r.get("trial_type") == "go"]
    nogo_rows = [r for r in rows if r.get("trial_type") == "nogo"]

    go_accuracy = proportion_or_blank([int(r.get("correct", 0)) for r in go_rows])
    go_omission = proportion_or_blank([int(r.get("missed", 0)) for r in go_rows])
    nogo_false_alarm = proportion_or_blank([int(r.get("commission_error", 0)) for r in nogo_rows])
    correct_go_rt = [r.get("rt_sec") for r in go_rows if r.get("correct") == 1 and r.get("rt_sec") not in [None, ""]]
    mean_correct_go_rt = mean_or_blank(correct_go_rt)

    return {
        "n_trials": len(rows),
        "n_go": len(go_rows),
        "n_nogo": len(nogo_rows),
        "go_accuracy": go_accuracy,
        "go_omission_rate": go_omission,
        "nogo_false_alarm_rate": nogo_false_alarm,
        "mean_correct_go_rt_sec": mean_correct_go_rt,
    }


def update_difficulty(level, recent_rows):
    metrics = evaluate_performance(recent_rows)
    action = "hold"
    old_level = level

    go_acc = metrics["go_accuracy"]
    go_omission = metrics["go_omission_rate"]
    nogo_fa = metrics["nogo_false_alarm_rate"]
    mean_rt = metrics["mean_correct_go_rt_sec"]

    has_minimum_data = metrics["n_go"] >= 8 and metrics["n_nogo"] >= 2

    if has_minimum_data:
        if (
            go_acc != "" and nogo_fa != "" and mean_rt != "" and
            go_acc >= HARDER_GO_ACCURACY and
            nogo_fa <= HARDER_NOGO_FALSE_ALARM and
            mean_rt <= HARDER_MEAN_GO_RT_SEC and
            (go_omission == "" or go_omission <= HARDER_GO_OMISSION)
        ):
            level = min(len(DIFFICULTY_LEVELS), level + 1)
            action = "increase_difficulty" if level != old_level else "hold_at_max"
        elif (
            (go_acc != "" and go_acc < EASIER_GO_ACCURACY) or
            (go_omission != "" and go_omission > EASIER_GO_OMISSION) or
            (nogo_fa != "" and nogo_fa > EASIER_NOGO_FALSE_ALARM)
        ):
            level = max(1, level - 1)
            action = "decrease_difficulty" if level != old_level else "hold_at_min"

    metrics.update({
        "old_difficulty_level": old_level,
        "new_difficulty_level": level,
        "adaptive_action": action,
    })
    return level, action, metrics


def trial_stimulus_arrows(trial_type, congruency, target_direction):
    center_arrow = "<" if target_direction == "left" else ">"
    if congruency == "congruent":
        flanker_arrow = center_arrow
    else:
        flanker_arrow = ">" if target_direction == "left" else "<"

    arrows = [flanker_arrow, flanker_arrow, center_arrow, flanker_arrow, flanker_arrow]
    center_color = NOGO_TARGET_COLOR if trial_type == "nogo" else GO_TARGET_COLOR
    return arrows, center_color


def draw_flanker_stimulus(arrow_stims, trial_type, congruency, target_direction):
    arrows, center_color = trial_stimulus_arrows(trial_type, congruency, target_direction)
    for idx, stim in enumerate(arrow_stims):
        stim.text = arrows[idx]
        stim.color = center_color if idx == 2 else FLANKER_COLOR
        stim.draw()


def draw_blank_with_marker(win, blank_marker, progress_text=None):
    if progress_text is not None:
        progress_text.draw()
    blank_marker.draw()
    win.flip()


def run_trial(win, kb, arrow_stims, blank_marker, progress_text, phase, trial_num, trial,
              difficulty_level, phase_clock, phase_duration_sec, global_clock,
              file_stem, participant_number, visit, block, date_yyyymmdd, event_rows,
              practice_round=""):
    """Runs one flanker Go/No-Go trial and returns a row plus escape flag."""
    settings = get_level_settings(difficulty_level)
    trial_type = trial["trial_type"]
    congruency = trial["congruency"]
    target_direction = trial["target_direction"]
    stim_duration_sec = settings["stim_duration_sec"]
    response_window_sec = settings["response_window_sec"]
    isi_sec = random.choice(settings["isi_options_sec"])

    correct_key = "1" if target_direction == "left" else "4"
    onset_name = onset_trigger_name(phase, trial_type, congruency, target_direction)
    onset_trigger = TRIGGERS[onset_name]

    # Pre-trial fixation/ISI.
    if progress_text is not None:
        progress_text.text = f"Trial {trial_num}"
        progress_text.draw()
    fixation.draw()
    win.flip()
    if not bounded_wait(isi_sec):
        return None, True

    if phase_clock.getTime() >= phase_duration_sec:
        return None, False

    event.clearEvents(eventType="keyboard")
    kb.clearEvents()

    # Draw and flip the stimulus. Reset the keyboard clock and send the onset trigger
    # on the same screen refresh.
    if progress_text is not None:
        progress_text.draw()
    draw_flanker_stimulus(arrow_stims, trial_type, congruency, target_direction)
    win.callOnFlip(kb.clock.reset)
    win.callOnFlip(send_trigger, onset_trigger)
    win.flip()

    trial_onset_phase_time = phase_clock.getTime()
    trial_onset_global_time = global_clock.getTime()
    trial_onset_iso = now_iso()
    trial_onset_unix = now_unix()

    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        phase, "stimulus_onset", onset_trigger, phase_clock, global_clock,
        extra={
            "practice_round": practice_round,
            "trial_num": trial_num,
            "trial_type": trial_type,
            "congruency": congruency,
            "target_direction": target_direction,
            "difficulty_level": difficulty_level,
            "stim_duration_sec": stim_duration_sec,
            "response_window_sec": response_window_sec,
            "isi_sec": isi_sec,
        },
    )

    responded = 0
    response_key = ""
    response_side = ""
    response_rt_sec = ""
    response_phase_time = ""
    response_global_time = ""
    response_trigger = ""
    response_iso = ""
    response_unix = ""
    escaped = False

    stimulus_visible = True
    blank_drawn = False

    # Continue collecting response until the response window ends or the phase ends.
    while kb.clock.getTime() < response_window_sec and phase_clock.getTime() < phase_duration_sec:
        elapsed = kb.clock.getTime()

        if elapsed < stim_duration_sec:
            if progress_text is not None:
                progress_text.draw()
            draw_flanker_stimulus(arrow_stims, trial_type, congruency, target_direction)
            win.flip()
        else:
            stimulus_visible = False
            if not blank_drawn:
                draw_blank_with_marker(win, blank_marker, progress_text)
                blank_drawn = True
            else:
                core.wait(0.001)

        keys = kb.getKeys(keyList=RESPONSE_KEYS + [QUIT_KEY], waitRelease=False, clear=True)
        if keys:
            for key in keys:
                if key.name == QUIT_KEY:
                    escaped = True
                    break
                if key.name in RESPONSE_KEYS and not responded:
                    responded = 1
                    response_key = key.name
                    response_side = key_to_response(key.name)
                    response_rt_sec = round(key.rt, 6)
                    response_phase_time = round(phase_clock.getTime(), 6)
                    response_global_time = round(global_clock.getTime(), 6)
                    response_iso = now_iso()
                    response_unix = round(now_unix(), 6)
                    response_trigger = TRIGGERS[response_trigger_name(phase, response_side)]
                    send_trigger(response_trigger)
                    add_event(
                        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
                        phase, "response", response_trigger, phase_clock, global_clock,
                        extra={
                            "practice_round": practice_round,
                            "trial_num": trial_num,
                            "trial_type": trial_type,
                            "congruency": congruency,
                            "target_direction": target_direction,
                            "difficulty_level": difficulty_level,
                            "response_key": response_key,
                            "response_side": response_side,
                            "response_rt_sec": response_rt_sec,
                        },
                    )
                    # Keep the trial duration fixed after the first response.
                    break
            if escaped:
                break

    if stimulus_visible:
        draw_blank_with_marker(win, blank_marker, progress_text)

    # Scoring.
    if trial_type == "go":
        correct = int(responded == 1 and response_side == target_direction)
        missed = int(responded == 0)
        wrong_response = int(responded == 1 and response_side != target_direction)
        commission_error = 0
        inhibition_success = ""
    else:
        correct = int(responded == 0)
        missed = 0
        wrong_response = 0
        commission_error = int(responded == 1)
        inhibition_success = int(responded == 0)

    trial_offset_phase_time = phase_clock.getTime()
    trial_offset_global_time = global_clock.getTime()
    trial_offset_iso = now_iso()
    trial_offset_unix = now_unix()

    arrows, center_color = trial_stimulus_arrows(trial_type, congruency, target_direction)
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
        "trial_type": trial_type,
        "congruency": congruency,
        "target_direction": target_direction,
        "correct_key": correct_key if trial_type == "go" else "none",
        "stimulus_string": "".join(arrows),
        "center_color": center_color,
        "difficulty_level": difficulty_level,
        "stim_duration_sec": stim_duration_sec,
        "response_window_sec": response_window_sec,
        "isi_sec": isi_sec,
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
        "response_side": response_side,
        "rt_sec": response_rt_sec,
        "response_phase_time_sec": response_phase_time,
        "response_global_time_sec": response_global_time,
        "response_iso": response_iso,
        "response_unix_time_sec": response_unix,
        "correct": correct,
        "missed": missed,
        "wrong_response": wrong_response,
        "commission_error": commission_error,
        "inhibition_success": inhibition_success,
        "onset_trigger_name": onset_name,
        "onset_trigger": onset_trigger,
        "response_trigger": response_trigger,
    }
    return row, escaped


def show_practice_feedback(win, feedback_stim, row, remaining_sec):
    if row is None:
        return True

    if row["trial_type"] == "go":
        if row["correct"] == 1:
            msg = "Correct"
        elif row["missed"] == 1:
            msg = "Too slow / no response"
        else:
            msg = "Incorrect button"
    else:
        if row["correct"] == 1:
            msg = "Correct: no response"
        else:
            msg = "Do not press for a RED center arrow"

    feedback_stim.setText(msg)
    feedback_stim.draw()
    win.flip()
    return bounded_wait(min(PRACTICE_FEEDBACK_SEC, max(0, remaining_sec)))


def summarize_rows(rows, prefix):
    go_rows = [r for r in rows if r.get("trial_type") == "go"]
    nogo_rows = [r for r in rows if r.get("trial_type") == "nogo"]
    cong_go_rows = [r for r in go_rows if r.get("congruency") == "congruent"]
    incong_go_rows = [r for r in go_rows if r.get("congruency") == "incongruent"]
    cong_nogo_rows = [r for r in nogo_rows if r.get("congruency") == "congruent"]
    incong_nogo_rows = [r for r in nogo_rows if r.get("congruency") == "incongruent"]

    correct_go_rt = [r["rt_sec"] for r in go_rows if r.get("correct") == 1 and r.get("rt_sec") not in ["", None]]
    cong_go_rt = [r["rt_sec"] for r in cong_go_rows if r.get("correct") == 1 and r.get("rt_sec") not in ["", None]]
    incong_go_rt = [r["rt_sec"] for r in incong_go_rows if r.get("correct") == 1 and r.get("rt_sec") not in ["", None]]

    cong_mean = mean_or_blank(cong_go_rt)
    incong_mean = mean_or_blank(incong_go_rt)
    flanker_effect = ""
    if cong_mean != "" and incong_mean != "":
        flanker_effect = round(incong_mean - cong_mean, 6)

    difficulty_vals = [r.get("difficulty_level") for r in rows if r.get("difficulty_level") not in ["", None]]
    final_third = rows[int(len(rows) * (2 / 3)):] if rows else []
    final_third_difficulty = [r.get("difficulty_level") for r in final_third if r.get("difficulty_level") not in ["", None]]

    out = {
        f"{prefix}_n_trials": len(rows),
        f"{prefix}_n_go_trials": len(go_rows),
        f"{prefix}_n_nogo_trials": len(nogo_rows),
        f"{prefix}_overall_accuracy": proportion_or_blank([int(r.get("correct", 0)) for r in rows]),
        f"{prefix}_go_accuracy": proportion_or_blank([int(r.get("correct", 0)) for r in go_rows]),
        f"{prefix}_go_omission_rate": proportion_or_blank([int(r.get("missed", 0)) for r in go_rows]),
        f"{prefix}_go_wrong_response_rate": proportion_or_blank([int(r.get("wrong_response", 0)) for r in go_rows]),
        f"{prefix}_nogo_accuracy": proportion_or_blank([int(r.get("correct", 0)) for r in nogo_rows]),
        f"{prefix}_nogo_commission_rate": proportion_or_blank([int(r.get("commission_error", 0)) for r in nogo_rows]),
        f"{prefix}_mean_rt_correct_go_sec": mean_or_blank(correct_go_rt),
        f"{prefix}_sd_rt_correct_go_sec": sd_or_blank(correct_go_rt),
        f"{prefix}_mean_rt_congruent_go_sec": mean_or_blank(cong_go_rt),
        f"{prefix}_mean_rt_incongruent_go_sec": mean_or_blank(incong_go_rt),
        f"{prefix}_flanker_interference_rt_sec": flanker_effect,
        f"{prefix}_congruent_go_accuracy": proportion_or_blank([int(r.get("correct", 0)) for r in cong_go_rows]),
        f"{prefix}_incongruent_go_accuracy": proportion_or_blank([int(r.get("correct", 0)) for r in incong_go_rows]),
        f"{prefix}_congruent_nogo_commission_rate": proportion_or_blank([int(r.get("commission_error", 0)) for r in cong_nogo_rows]),
        f"{prefix}_incongruent_nogo_commission_rate": proportion_or_blank([int(r.get("commission_error", 0)) for r in incong_nogo_rows]),
        f"{prefix}_mean_difficulty_level": mean_or_blank(difficulty_vals),
        f"{prefix}_first_trial_difficulty_level": rows[0].get("difficulty_level", "") if rows else "",
        f"{prefix}_last_trial_difficulty_level": rows[-1].get("difficulty_level", "") if rows else "",
        f"{prefix}_final_third_mean_difficulty_level": mean_or_blank(final_third_difficulty),
    }

    # Left/right checks are useful for response-pad mapping QC.
    for direction in ["left", "right"]:
        direction_go = [r for r in go_rows if r.get("target_direction") == direction]
        direction_rt = [r["rt_sec"] for r in direction_go if r.get("correct") == 1 and r.get("rt_sec") not in ["", None]]
        out[f"{prefix}_{direction}_go_n_trials"] = len(direction_go)
        out[f"{prefix}_{direction}_go_accuracy"] = proportion_or_blank([int(r.get("correct", 0)) for r in direction_go])
        out[f"{prefix}_{direction}_go_mean_rt_correct_sec"] = mean_or_blank(direction_rt)

    return out


def calculate_outcomes(trial_rows, adaptive_rows):
    practice_rows = [r for r in trial_rows if r.get("phase") == "practice"]
    main_rows = [r for r in trial_rows if r.get("phase") == "main"]
    outcomes = {}
    outcomes.update(summarize_rows(practice_rows, "practice"))
    outcomes.update(summarize_rows(main_rows, "main"))

    main_adapt = [r for r in adaptive_rows if r.get("phase") == "main"]
    outcomes["main_n_adaptive_updates"] = len(main_adapt)
    outcomes["main_n_difficulty_increases"] = sum(1 for r in main_adapt if r.get("adaptive_action") == "increase_difficulty")
    outcomes["main_n_difficulty_decreases"] = sum(1 for r in main_adapt if r.get("adaptive_action") == "decrease_difficulty")
    outcomes["main_adaptive_actions"] = ";".join(str(r.get("adaptive_action", "")) for r in main_adapt)
    outcomes["main_difficulty_sequence"] = ";".join(str(r.get("new_difficulty_level", "")) for r in main_adapt)
    return outcomes


def write_csv(path, rows, first_fields=None):
    first_fields = first_fields or []
    if rows:
        all_fields = sorted(set().union(*(row.keys() for row in rows)))
        fieldnames = first_fields + [f for f in all_fields if f not in first_fields]
    else:
        fieldnames = first_fields

    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)

# -------------------------
# Participant / session dialog
# -------------------------

today_yyyymmdd = datetime.now().strftime("%Y%m%d")

exp_info = {
    "participant_number": "001",
    "visit": "B",
    "block": "FGNG",
    "date_YYYYMMDD": today_yyyymmdd,
}

dlg = gui.DlgFromDict(dictionary=exp_info, title="Adaptive Flanker Go/No-Go Task")
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
summary_file = os.path.join(output_dir, f"{file_stem}_summary.csv")
adaptive_file = os.path.join(output_dir, f"{file_stem}_adaptive_updates.csv")

# -------------------------
# Window and stimuli
# -------------------------

win = visual.Window(
    size=(1200, 800),
    fullscr=FULLSCREEN,
    screen=SCREEN_INDEX,
    color=BACKGROUND_COLOR,
    units="height",
)

kb = keyboard.Keyboard()

instructions = visual.TextStim(
    win,
    text=(
        "Flanker Go/No-Go Task\n\n"
        "Focus on the CENTER arrow only. Ignore the surrounding arrows.\n\n"
        "If the CENTER arrow points LEFT, press the LEFT / BLUE button (1).\n"
        "If the CENTER arrow points RIGHT, press the RIGHT / RED button (4).\n\n"
        "If the CENTER arrow is RED, do not press anything.\n\n"
        "The display will be brief, and the task will adapt based on performance.\n"
        "Please respond as quickly and accurately as possible.\n\n"
        "You will first complete a brief practice round with feedback.\n\n"
        "Researcher: press SPACE to begin practice."
    ),
    color="white",
    height=0.036,
    wrapWidth=1.35,
)

practice_transition_text = visual.TextStim(
    win,
    text="",
    color="white",
    height=0.038,
    wrapWidth=1.35,
)

practice_repeat_note = visual.TextStim(
    win,
    text="Practice can be repeated with R, up to 3 times.",
    color="white",
    height=0.022,
    pos=(0, -0.42),
    wrapWidth=1.25,
    italic=True,
)

fixation = visual.TextStim(win, text="+", color=FIXATION_COLOR, height=0.08)
feedback_text = visual.TextStim(win, text="", color="white", height=0.055, wrapWidth=1.25)
blank_marker = visual.TextStim(win, text="", color="white", height=0.035)
progress_text = visual.TextStim(win, text="", color="gray", height=0.026, pos=(0, 0.43))
end_text = visual.TextStim(
    win,
    text="Flanker Go/No-Go Task Complete\n\nResearcher: press SPACE to exit.",
    color="white",
    height=0.04,
    wrapWidth=1.25,
)

arrow_stims = []
for x in ARROW_X_POSITIONS:
    arrow_stims.append(
        visual.TextStim(
            win,
            text="",
            pos=(x, STIM_Y),
            color="white",
            height=ARROW_HEIGHT,
            font="Courier New",
        )
    )

# -------------------------
# Instructions
# -------------------------

instructions.draw()
win.flip()

if not wait_for_researcher_space_or_escape():
    win.close()
    core.quit()

trial_rows = []
event_rows = []
adaptive_rows = []
global_clock = core.Clock()
escaped = False

# -------------------------
# Practice execution
# -------------------------

practice_rounds_completed = 0
practice_repeats_used = 0
total_practice_trials_completed = 0
practice_total_actual_duration_sec = 0.0
practice_start_iso = ""
practice_start_unix_sec = ""
practice_end_iso = ""
practice_end_unix_sec = ""
practice_final_difficulty_level = PRACTICE_START_DIFFICULTY_LEVEL
practice_trial_num = 0

while not escaped:
    practice_rounds_completed += 1
    practice_round = practice_rounds_completed
    practice_repeat_index = max(0, practice_round - 1)
    practice_difficulty_level = PRACTICE_START_DIFFICULTY_LEVEL
    practice_recent_rows = []
    practice_trial_bag = []
    practice_trial_num = 0

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
        extra={"practice_round": practice_round, "practice_repeat_index": practice_repeat_index},
    )

    event.clearEvents(eventType="keyboard")
    kb.clearEvents()

    # Initial delay before the first trial.
    fixation.draw()
    win.flip()
    if not bounded_wait(min(INITIAL_START_DELAY_SEC, PRACTICE_DURATION_SEC)):
        escaped = True
        break

    while practice_clock.getTime() < PRACTICE_DURATION_SEC:
        if PRACTICE_DURATION_SEC - practice_clock.getTime() < MIN_REMAINING_TO_START_TRIAL_SEC:
            break

        if not practice_trial_bag:
            practice_trial_bag = build_trial_bag(practice_difficulty_level, PRACTICE_ADAPT_WINDOW_N_TRIALS)

        trial = practice_trial_bag.pop(0)
        practice_trial_num += 1

        row, trial_escaped = run_trial(
            win, kb, arrow_stims, blank_marker, None, "practice", practice_trial_num, trial,
            practice_difficulty_level, practice_clock, PRACTICE_DURATION_SEC, global_clock,
            file_stem, participant_number, visit, block, date_yyyymmdd, event_rows,
            practice_round=practice_round,
        )

        if trial_escaped:
            escaped = True
            break

        if row is not None:
            row.update({
                "practice_round": practice_round,
                "practice_repeat_index": practice_repeat_index,
                "difficulty_level_after_update": practice_difficulty_level,
                "adaptive_action": "pending",
            })
            trial_rows.append(row)
            practice_recent_rows.append(row)

            remaining = PRACTICE_DURATION_SEC - practice_clock.getTime()
            if not show_practice_feedback(win, feedback_text, row, remaining):
                escaped = True
                break

            if (
                len(practice_recent_rows) >= PRACTICE_ADAPT_WINDOW_N_TRIALS and
                practice_trial_num % PRACTICE_ADAPT_CHECK_INTERVAL_N_TRIALS == 0
            ):
                old_level = practice_difficulty_level
                practice_difficulty_level, action, metrics = update_difficulty(practice_difficulty_level, practice_recent_rows[-PRACTICE_ADAPT_WINDOW_N_TRIALS:])
                practice_final_difficulty_level = practice_difficulty_level
                adaptive_row = {
                    "file_stem": file_stem,
                    "participant_id": f"MLI{participant_number}",
                    "participant_number": participant_number,
                    "visit": visit,
                    "block": block,
                    "date_YYYYMMDD": date_yyyymmdd,
                    "task_name": TASK_NAME,
                    "phase": "practice",
                    "practice_round": practice_round,
                    "trial_num_at_update": practice_trial_num,
                    "old_difficulty_level": old_level,
                    "new_difficulty_level": practice_difficulty_level,
                    "adaptive_action": action,
                    "phase_time_sec": round(practice_clock.getTime(), 6),
                    "global_time_sec": round(global_clock.getTime(), 6),
                }
                adaptive_row.update(metrics)
                adaptive_rows.append(adaptive_row)
                add_event(
                    event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
                    "practice", "adaptive_update", "", practice_clock, global_clock,
                    extra=adaptive_row,
                )
                # Keep rows for rolling-window adaptation rather than resetting after each update.
                if practice_difficulty_level != old_level:
                    practice_trial_bag = []

    this_practice_end_iso = now_iso()
    this_practice_end_unix_sec = now_unix()
    practice_actual_duration_sec = practice_clock.getTime()
    practice_total_actual_duration_sec += practice_actual_duration_sec
    total_practice_trials_completed += practice_trial_num
    practice_end_iso = this_practice_end_iso
    practice_end_unix_sec = this_practice_end_unix_sec
    practice_final_difficulty_level = practice_difficulty_level

    send_trigger(TRIGGERS["practice_end"])
    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        "practice", "practice_end", TRIGGERS["practice_end"], practice_clock, global_clock,
        extra={
            "actual_duration_sec": round(practice_actual_duration_sec, 6),
            "practice_round": practice_round,
            "practice_repeat_index": practice_repeat_index,
            "n_practice_trials_completed": practice_trial_num,
            "practice_final_difficulty_level": practice_difficulty_level,
        },
    )

    if escaped:
        break

    if practice_repeats_used < MAX_PRACTICE_REPEATS:
        practice_transition_text.setText(
            "Practice complete.\n\n"
            "The real task will begin next.\n\n"
            "Remember:\n"
            "Center arrow points left = press 1 / left.\n"
            "Center arrow points right = press 4 / right.\n"
            "RED center arrow = do not press.\n\n"
            "There will be no feedback during the real task.\n\n"
            "Researcher: press SPACE to begin the task, or press R to repeat practice."
        )
    else:
        practice_transition_text.setText(
            "Practice complete.\n\n"
            "The real task will begin next.\n\n"
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

main_trial_num = 0
main_difficulty_level = START_DIFFICULTY_LEVEL
main_recent_rows = []
main_trial_bag = []

if not escaped:
    task_clock = core.Clock()
    task_start_iso = now_iso()
    task_start_unix_sec = now_unix()

    send_trigger(TRIGGERS["task_start"])
    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        "main", "task_start", TRIGGERS["task_start"], task_clock, global_clock,
        extra={"start_difficulty_level": main_difficulty_level},
    )
    event.clearEvents(eventType="keyboard")
    kb.clearEvents()

    fixation.draw()
    win.flip()
    if not bounded_wait(min(INITIAL_START_DELAY_SEC, TASK_DURATION_SEC)):
        escaped = True

    while not escaped and task_clock.getTime() < TASK_DURATION_SEC:
        if TASK_DURATION_SEC - task_clock.getTime() < MIN_REMAINING_TO_START_TRIAL_SEC:
            break

        if not main_trial_bag:
            main_trial_bag = build_trial_bag(main_difficulty_level, ADAPT_WINDOW_N_TRIALS)

        trial = main_trial_bag.pop(0)
        main_trial_num += 1

        row, trial_escaped = run_trial(
            win, kb, arrow_stims, blank_marker, None, "main", main_trial_num, trial,
            main_difficulty_level, task_clock, TASK_DURATION_SEC, global_clock,
            file_stem, participant_number, visit, block, date_yyyymmdd, event_rows,
        )

        if trial_escaped:
            escaped = True
            break

        if row is not None:
            row.update({
                "difficulty_level_after_update": main_difficulty_level,
                "adaptive_action": "pending",
            })
            trial_rows.append(row)
            main_recent_rows.append(row)

            if (
                len(main_recent_rows) >= ADAPT_WINDOW_N_TRIALS and
                main_trial_num % ADAPT_CHECK_INTERVAL_N_TRIALS == 0
            ):
                old_level = main_difficulty_level
                main_difficulty_level, action, metrics = update_difficulty(main_difficulty_level, main_recent_rows[-ADAPT_WINDOW_N_TRIALS:])
                adaptive_row = {
                    "file_stem": file_stem,
                    "participant_id": f"MLI{participant_number}",
                    "participant_number": participant_number,
                    "visit": visit,
                    "block": block,
                    "date_YYYYMMDD": date_yyyymmdd,
                    "task_name": TASK_NAME,
                    "phase": "main",
                    "trial_num_at_update": main_trial_num,
                    "old_difficulty_level": old_level,
                    "new_difficulty_level": main_difficulty_level,
                    "adaptive_action": action,
                    "phase_time_sec": round(task_clock.getTime(), 6),
                    "global_time_sec": round(global_clock.getTime(), 6),
                }
                adaptive_row.update(metrics)
                adaptive_rows.append(adaptive_row)
                add_event(
                    event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
                    "main", "adaptive_update", "", task_clock, global_clock,
                    extra=adaptive_row,
                )
                # Keep rows for rolling-window adaptation rather than resetting after each update.
                # Force a new trial bag only when the difficulty level changes so the new level affects trial mix immediately.
                if main_difficulty_level != old_level:
                    main_trial_bag = []

    task_end_iso = now_iso()
    task_end_unix_sec = now_unix()
    actual_duration_sec = task_clock.getTime() if 'task_clock' in locals() else 0
    send_trigger(TRIGGERS["task_end"])
    add_event(
        event_rows, file_stem, participant_number, visit, block, date_yyyymmdd,
        "main", "task_end", TRIGGERS["task_end"], task_clock, global_clock,
        extra={
            "actual_duration_sec": round(actual_duration_sec, 6),
            "completed": int((actual_duration_sec >= TASK_DURATION_SEC) and not escaped),
            "n_trials_completed": main_trial_num,
            "final_difficulty_level": main_difficulty_level,
        },
    )
else:
    task_start_iso = ""
    task_start_unix_sec = ""
    task_end_iso = ""
    task_end_unix_sec = ""
    actual_duration_sec = 0

# -------------------------
# Save files
# -------------------------

trial_first_fields = [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "phase", "practice_round", "practice_repeat_index", "trial_num", "trial_type",
    "congruency", "target_direction", "correct_key", "stimulus_string", "center_color",
    "difficulty_level", "difficulty_level_after_update", "adaptive_action", "stim_duration_sec",
    "response_window_sec", "isi_sec", "responded", "response_key", "response_side",
    "rt_sec", "correct", "missed", "wrong_response", "commission_error", "inhibition_success",
    "onset_trigger_name", "onset_trigger", "response_trigger",
]
write_csv(trials_file, trial_rows, trial_first_fields)

adaptive_first_fields = [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "phase", "practice_round", "trial_num_at_update", "old_difficulty_level",
    "new_difficulty_level", "adaptive_action", "go_accuracy", "go_omission_rate",
    "nogo_false_alarm_rate", "mean_correct_go_rt_sec",
]
write_csv(adaptive_file, adaptive_rows, adaptive_first_fields)

write_csv(events_file, event_rows, [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "phase", "event_name", "trigger_code", "trial_num", "trial_type",
    "congruency", "target_direction", "response_side", "response_rt_sec",
    "phase_time_sec", "psychopy_global_clock_sec", "iso_time", "unix_time_sec",
])

outcomes = calculate_outcomes(trial_rows, adaptive_rows)
outcomes.update({
    "file_stem": file_stem,
    "participant_id": f"MLI{participant_number}",
    "participant_number": participant_number,
    "visit": visit,
    "block": block,
    "date_YYYYMMDD": date_yyyymmdd,
    "task_name": TASK_NAME,
    "main_planned_duration_sec": TASK_DURATION_SEC,
    "practice_planned_duration_sec": PRACTICE_DURATION_SEC,
    "main_start_difficulty_level_setting": START_DIFFICULTY_LEVEL,
    "practice_start_difficulty_level_setting": PRACTICE_START_DIFFICULTY_LEVEL,
    "adapt_check_interval_n_trials_setting": ADAPT_CHECK_INTERVAL_N_TRIALS,
    "adapt_window_n_trials_setting": ADAPT_WINDOW_N_TRIALS,
    "practice_adapt_check_interval_n_trials_setting": PRACTICE_ADAPT_CHECK_INTERVAL_N_TRIALS,
    "practice_adapt_window_n_trials_setting": PRACTICE_ADAPT_WINDOW_N_TRIALS,
    "harder_go_accuracy_setting": HARDER_GO_ACCURACY,
    "harder_nogo_false_alarm_setting": HARDER_NOGO_FALSE_ALARM,
    "harder_mean_go_rt_sec_setting": HARDER_MEAN_GO_RT_SEC,
    "harder_go_omission_setting": HARDER_GO_OMISSION,
    "easier_go_accuracy_setting": EASIER_GO_ACCURACY,
    "easier_nogo_false_alarm_setting": EASIER_NOGO_FALSE_ALARM,
    "easier_go_omission_setting": EASIER_GO_OMISSION,
    "trigger_values_all_under_255": int(max(TRIGGERS.values()) <= 255),
})
outcome_first_fields = [
    "file_stem", "participant_id", "participant_number", "visit", "block", "date_YYYYMMDD",
    "task_name", "main_planned_duration_sec", "practice_planned_duration_sec",
    "main_start_difficulty_level_setting", "practice_start_difficulty_level_setting",
]
write_csv(outcomes_file, [outcomes], outcome_first_fields)

summary_rows = [{
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
    "practice_start_unix_sec": round(practice_start_unix_sec, 6) if practice_start_unix_sec != "" else "",
    "practice_end_unix_sec": round(practice_end_unix_sec, 6) if practice_end_unix_sec != "" else "",
    "n_practice_trials_completed": total_practice_trials_completed,
    "practice_final_difficulty_level": practice_final_difficulty_level,
    "main_planned_duration_sec": TASK_DURATION_SEC,
    "main_actual_duration_sec": round(actual_duration_sec, 6),
    "main_start_iso": task_start_iso,
    "main_end_iso": task_end_iso,
    "main_start_unix_sec": round(task_start_unix_sec, 6) if task_start_unix_sec != "" else "",
    "main_end_unix_sec": round(task_end_unix_sec, 6) if task_end_unix_sec != "" else "",
    "completed": int((actual_duration_sec >= TASK_DURATION_SEC) and not escaped),
    "escaped": int(escaped),
    "n_main_trials_completed": main_trial_num,
    "final_difficulty_level": main_difficulty_level,
    "trials_file": trials_file,
    "events_file": events_file,
    "outcomes_file": outcomes_file,
    "adaptive_file": adaptive_file,
}]
write_csv(summary_file, summary_rows)

# -------------------------
# End screen
# -------------------------

main_rows = [r for r in trial_rows if r.get("phase") == "main"]
main_summary = summarize_rows(main_rows, "main") if main_rows else {}

summary_message = (
    "Flanker Go/No-Go Task Complete\n\n"
    f"Main trials completed: {main_summary.get('main_n_trials', 0)}\n"
    f"Go accuracy: {main_summary.get('main_go_accuracy', 'N/A')}\n"
    f"No-Go commission rate: {main_summary.get('main_nogo_commission_rate', 'N/A')}\n"
    f"Mean correct Go RT: {main_summary.get('main_mean_rt_correct_go_sec', 'N/A')} sec\n"
    f"Final difficulty level: {main_difficulty_level}\n\n"
    f"CSV files saved in: {output_dir}\n\n"
    "Researcher: press SPACE to close."
)

end_text.setText(summary_message)
end_text.draw()
win.flip()
wait_for_researcher_space_or_escape()

win.close()
core.quit()
