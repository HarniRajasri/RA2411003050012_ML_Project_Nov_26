"""Load and clean a recorded EEG file with MNE-Python."""
from __future__ import annotations

import logging
from pathlib import Path

import mne

from config import H_FREQ, L_FREQ, NON_EEG_HINTS

log = logging.getLogger("khorizon.eeg.pre")


def load_raw(path: str | Path) -> "mne.io.BaseRaw":
    """Read a BDF or EDF file. Raises a clear error for missing or unsupported files."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"EEG file not found: {p}\n"
            "Pass the file explicitly, e.g.  python feature_extraction.py --input E:\\path\\to\\file.bdf")
    ext = p.suffix.lower()
    if ext == ".bdf":
        return mne.io.read_raw_bdf(p, preload=True, verbose="ERROR")
    if ext == ".edf":
        return mne.io.read_raw_edf(p, preload=True, verbose="ERROR")
    raise ValueError(f"Unsupported EEG file type '{ext}'. Use .bdf or .edf.")


def select_eeg_channels(raw: "mne.io.BaseRaw", channels: list[str] | None = None) -> "mne.io.BaseRaw":
    """Keep scalp EEG channels only. `channels` (case-insensitive names) restricts the selection further."""
    names = raw.ch_names
    if channels:
        wanted = {c.lower() for c in channels}
        keep = [n for n in names if n.lower() in wanted]
        missing = sorted(wanted - {n.lower() for n in keep})
        if missing:
            log.warning("channels not found and ignored: %s", ", ".join(missing))
        if not keep:
            raise ValueError("None of the requested channels exist in this recording. Available: " + ", ".join(names[:20]) + " ...")
    else:
        keep = [n for n in names if not any(h in n.lower() for h in NON_EEG_HINTS)]
        if not keep:
            raise ValueError("No EEG channels left after removing trigger/auxiliary channels.")
    return raw.copy().pick(keep)


def bandpass(raw: "mne.io.BaseRaw", l_freq: float = L_FREQ, h_freq: float = H_FREQ) -> "mne.io.BaseRaw":
    nyq = raw.info["sfreq"] / 2.0
    if h_freq >= nyq:
        h_freq = nyq - 1.0
        log.warning("high cut-off lowered to %.1f Hz (Nyquist limit)", h_freq)
    out = raw.copy()
    out.filter(l_freq=l_freq, h_freq=h_freq, verbose="ERROR")
    return out


def preprocess(path: str | Path, channels: list[str] | None = None, l_freq: float = L_FREQ,
               h_freq: float = H_FREQ, rereference: bool = True) -> "mne.io.BaseRaw":
    raw = load_raw(path)
    raw = select_eeg_channels(raw, channels)
    if rereference:
        raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    raw = bandpass(raw, l_freq, h_freq)
    log.info("preprocessed: %d channels, %.1f Hz, %.1f s", len(raw.ch_names), raw.info["sfreq"], raw.times[-1])
    return raw
