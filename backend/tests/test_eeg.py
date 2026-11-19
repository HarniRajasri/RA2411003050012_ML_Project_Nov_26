import csv
import math

from app.eeg.base import Normalizer
from app.eeg.dataset_replay import DatasetReplaySource
from app.eeg.manager import EEGManager
from app.config import Settings


def write_csv(path, n=20):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["window_start_s", "window_end_s", "delta", "theta", "alpha", "beta", "gamma", "engagement_index", "condition"])
        for i in range(n):
            beta = 0.2 + 0.01 * i
            w.writerow([i * 10, i * 10 + 10, 0.1, 0.1, 0.2, beta, 0.1, beta / 0.3, "test"])


def test_normalizer_monotonic_and_bounded():
    n = Normalizer([0.5, 0.8, 1.0, 1.2, 2.0])
    vals = [n.evidence(x) for x in (0.1, 0.5, 1.0, 2.0, 10.0)]
    assert vals == sorted(vals) and all(0.0 <= v <= 1.0 for v in vals)
    assert math.isclose(n.evidence(1.0), 0.5, abs_tol=0.05)


def test_replay_source_loads_and_labels(tmp_path):
    p = tmp_path / "f.csv"
    write_csv(p)
    src = DatasetReplaySource(str(p), 1.0)
    assert src.available and len(src.rows) == 20
    src._advance()
    st = src.status()
    assert st["mode"] == "DATASET_REPLAY" and "not live EEG" in st["label"] and 0 <= st["evidence"] <= 1


def test_replay_missing_file_degrades_gracefully(tmp_path):
    src = DatasetReplaySource(str(tmp_path / "nope.csv"))
    assert not src.available and "not found" in src.status()["message"]


def test_eeg_evidence_only_for_target_real_device(tmp_path):
    p = tmp_path / "f.csv"
    write_csv(p)
    s = Settings(eeg_mode="DATASET_REPLAY", eeg_replay_file=str(p), eeg_target_device="KH-S01")
    m = EEGManager(s)
    m.source._advance()
    assert m.evidence_for("KH-S01", "REAL") is not None
    assert m.evidence_for("KH-S02", "REAL") is None
    assert m.evidence_for("SIM-01", "SIMULATED") is None        # simulated students never get EEG evidence


def test_eeg_off_reports_motion_only():
    m = EEGManager(Settings(eeg_mode="OFF"))
    assert m.status()["mode"] == "OFF" and m.evidence_for("KH-S01", "REAL") is None
