"""Preview or push a feature CSV as if it were arriving in real time (software-in-the-loop).

    python dataset_replay.py --csv ../data/eeg_features/sub-01_ses-01.csv --step 1
    python dataset_replay.py --csv ... --push http://localhost:8000     (backend must run with EEG_MODE=PHYSICAL_EEG)

Normally you do NOT need this: set EEG_MODE=DATASET_REPLAY in .env and the backend replays the CSV itself.
This script is for checking a CSV and for exercising the push endpoint a future physical EEG driver would use.
Everything it prints is a replay of recorded data - not live EEG.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.request

from config import DEFAULT_OUTPUT


def load(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def evidence_fn(indices: list[float]):
    logs = [math.log(max(i, 1e-9)) for i in indices]
    med = statistics.median(logs)
    mad = statistics.median([abs(x - med) for x in logs]) or 0.0
    scale = max(1.4826 * mad, 1e-6)
    return lambda i: 0.5 * (1 + math.tanh(((math.log(max(i, 1e-9)) - med) / scale) / 2))


def push(url: str, row: dict) -> None:
    body = json.dumps({"source": "DATASET_REPLAY", **{k: float(row[k]) for k in ("delta", "theta", "alpha", "beta", "gamma")},
                       "condition": row.get("condition") or None}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/eeg/features", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        r.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--step", type=float, default=1.0, help="seconds between replayed windows")
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--push", default=None, help="backend base URL to POST features to")
    a = ap.parse_args(argv)
    try:
        rows = load(a.csv)
    except FileNotFoundError:
        print(f"ERROR: {a.csv} not found. Run feature_extraction.py first.", file=sys.stderr)
        return 2
    if not rows:
        print("ERROR: feature file is empty.", file=sys.stderr)
        return 2
    ev = evidence_fn([float(r["engagement_index"]) for r in rows])
    print("EEG DATASET REPLAY (software-in-the-loop) - recorded data, not live EEG")
    print(f"{'t(s)':>7} {'delta':>7} {'theta':>7} {'alpha':>7} {'beta':>7} {'gamma':>7} {'index':>7} {'evidence':>9}")
    for _ in range(a.loops):
        for r in rows:
            e = ev(float(r["engagement_index"]))
            print(f"{float(r['window_start_s']):7.1f} " + " ".join(f"{float(r[k]):7.3f}" for k in ("delta", "theta", "alpha", "beta", "gamma"))
                  + f" {float(r['engagement_index']):7.3f} {e:9.3f}")
            if a.push:
                try:
                    push(a.push, r)
                except (urllib.error.URLError, OSError) as exc:
                    print(f"  push failed: {exc}", file=sys.stderr)
            time.sleep(a.step)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
