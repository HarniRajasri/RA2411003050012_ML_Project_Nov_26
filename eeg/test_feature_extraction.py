"""Run with:  python -m pytest eeg  (needs numpy + scipy only)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feature_extraction import extract_features   # noqa: E402

SF = 128


def tone(freq, seconds=40, channels=4, noise=0.05):
    t = np.arange(int(seconds * SF)) / SF
    rng = np.random.default_rng(0)
    return np.vstack([np.sin(2 * np.pi * freq * t) + noise * rng.normal(size=t.size) for _ in range(channels)])


def test_alpha_tone_dominates_alpha_band():
    rows = extract_features(tone(10), SF, 10, 10)
    assert len(rows) == 4
    r = rows[0]
    assert r["alpha"] > 0.8 and r["beta"] < 0.1
    assert abs(sum(r[k] for k in ("delta", "theta", "alpha", "beta", "gamma")) - 1.0) < 1e-3


def test_beta_tone_gives_higher_engagement_index_than_alpha_tone():
    a = extract_features(tone(10), SF, 10, 10)[0]["engagement_index"]
    b = extract_features(tone(20), SF, 10, 10)[0]["engagement_index"]
    assert b > 10 * a


def test_window_bookkeeping_and_short_recording():
    rows = extract_features(tone(10, seconds=35), SF, 10, 5)
    assert [r["window_start_s"] for r in rows] == [0, 5, 10, 15, 20, 25]
    try:
        extract_features(tone(10, seconds=5), SF, 10, 10)
    except ValueError as exc:
        assert "shorter" in str(exc)
    else:
        raise AssertionError("expected ValueError")
