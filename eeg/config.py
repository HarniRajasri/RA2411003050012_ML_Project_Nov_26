"""Shared constants for the offline EEG feature pipeline.

The pipeline turns a recorded EEG file (BDF/EDF) into a small CSV of EEG-derived features (band powers and an
engagement index) that the KHorizon backend can replay. This is offline analysis of a public dataset - not live EEG.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Frequency bands in Hz (upper edge exclusive except gamma)
BANDS: dict[str, tuple[float, float]] = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 40.0),
}

# Band-pass filter applied before feature extraction
L_FREQ = 1.0
H_FREQ = 40.0

# Non-EEG / trigger channels commonly present in BioSemi BDF files
NON_EEG_HINTS = ("status", "trigger", "stim", "exg", "eog", "ecg", "emg", "gsr", "resp", "temp", "erg")

DEFAULT_WINDOW_SECONDS = 10.0
DEFAULT_STEP_SECONDS = 10.0

DEFAULT_INPUT = PROJECT_ROOT / "EEG" / "Experiment2" / "sub-01_ses-01_task-stim01_eeg.bdf"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "eeg_features" / "sub-01_ses-01.csv"

CSV_COLUMNS = ["window_start_s", "window_end_s", "delta", "theta", "alpha", "beta", "gamma",
               "engagement_index", "condition"]
