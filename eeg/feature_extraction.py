"""Offline EEG feature extraction: recorded BDF/EDF -> CSV of band powers per window.

    python feature_extraction.py --input <file.bdf> --output ../data/eeg_features/sub-01_ses-01.csv

For each window (default 10 s) the script estimates the power spectral density with Welch's method for every EEG
channel, averages across channels, and reports the *relative* power in delta, theta, alpha, beta and gamma plus
the engagement index beta / (alpha + theta).

These are EEG-derived features of a recorded public dataset. They are not a measurement of a student's attention.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import numpy as np
from scipy.signal import welch

from config import BANDS, CSV_COLUMNS, DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_STEP_SECONDS, DEFAULT_WINDOW_SECONDS, H_FREQ, L_FREQ

log = logging.getLogger("khorizon.eeg")


def band_powers(segment: np.ndarray, sfreq: float) -> dict[str, float]:
    """segment: (n_channels, n_samples). Returns relative band powers averaged over channels (sum ~= 1)."""
    nperseg = int(min(segment.shape[1], max(sfreq * 2, 64)))
    freqs, psd = welch(segment, fs=sfreq, nperseg=nperseg, noverlap=nperseg // 2, axis=-1)
    total_mask = (freqs >= BANDS["delta"][0]) & (freqs < BANDS["gamma"][1])
    df = freqs[1] - freqs[0]
    total = psd[:, total_mask].sum(axis=-1) * df
    out: dict[str, float] = {}
    for name, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        p = psd[:, m].sum(axis=-1) * df
        out[name] = float(np.mean(p / np.maximum(total, 1e-30)))
    return out


def engagement_index(bp: dict[str, float]) -> float:
    return bp["beta"] / max(bp["alpha"] + bp["theta"], 1e-12)


def extract_features(data: np.ndarray, sfreq: float, window_s: float = DEFAULT_WINDOW_SECONDS,
                     step_s: float = DEFAULT_STEP_SECONDS, condition: str = "") -> list[dict]:
    """Pure function (unit-tested): slide a window over (n_channels, n_samples) data."""
    if data.ndim != 2:
        raise ValueError("data must be 2-D (channels x samples)")
    if window_s <= 0 or step_s <= 0:
        raise ValueError("window and step must be positive")
    n = data.shape[1]
    w, s = int(round(window_s * sfreq)), int(round(step_s * sfreq))
    if n < w:
        raise ValueError(f"Recording ({n / sfreq:.1f} s) is shorter than one window ({window_s} s).")
    rows = []
    for start in range(0, n - w + 1, s):
        seg = data[:, start:start + w]
        bp = band_powers(seg, sfreq)
        rows.append({"window_start_s": round(start / sfreq, 3), "window_end_s": round((start + w) / sfreq, 3),
                     **{k: round(v, 6) for k, v in bp.items()}, "engagement_index": round(engagement_index(bp), 6),
                     "condition": condition})
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        wr.writeheader()
        wr.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract EEG band-power features from a BDF/EDF recording.")
    ap.add_argument("--input", "-i", default=str(DEFAULT_INPUT), help="BDF/EDF file (default: dataset location)")
    ap.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT), help="CSV output path")
    ap.add_argument("--window", type=float, default=DEFAULT_WINDOW_SECONDS, help="window length in seconds")
    ap.add_argument("--step", type=float, default=DEFAULT_STEP_SECONDS, help="step between windows in seconds")
    ap.add_argument("--channels", nargs="*", default=None, help="restrict to these channels (default: all EEG)")
    ap.add_argument("--l-freq", type=float, default=L_FREQ)
    ap.add_argument("--h-freq", type=float, default=H_FREQ)
    ap.add_argument("--no-reref", action="store_true", help="skip average re-referencing")
    ap.add_argument("--condition", default=None, help="label stored in the 'condition' column (default: file name)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    try:
        from preprocessing import preprocess
        raw = preprocess(a.input, a.channels, a.l_freq, a.h_freq, rereference=not a.no_reref)
        data = raw.get_data() * 1e6          # volts -> microvolts (relative powers are scale-free anyway)
        cond = a.condition or Path(a.input).stem
        rows = extract_features(data, raw.info["sfreq"], a.window, a.step, cond)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out = Path(a.output)
    write_csv(rows, out)
    idx = np.array([r["engagement_index"] for r in rows])
    print(f"Wrote {len(rows)} windows ({a.window:g}s each) to {out}")
    print(f"engagement_index  min={idx.min():.3f}  median={np.median(idx):.3f}  max={idx.max():.3f}")
    print("Label: EEG-derived features from a recorded dataset (replay) - not live EEG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
