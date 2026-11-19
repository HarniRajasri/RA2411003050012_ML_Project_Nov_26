# EEG module (dataset replay, software-in-the-loop)

There is **no physical EEG sensor** in this prototype. To show how one would fit in later, the backend can replay
EEG-derived features extracted from a recorded public dataset (Brain Body Behaviour, Experiment 2). Everything on
screen says *dataset replay* and never *live EEG*.

## 1. Extract features (offline)

The dataset file used during development: `sub-01_ses-01_task-stim01_eeg.bdf` (64 channels, 128 Hz, about 185 s).

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -WithEeg
.\scripts\extract_eeg_features.ps1 -InputFile "E:\College-projects\KHorizon\EEG\Experiment2\sub-01_ses-01_task-stim01_eeg.bdf"
```

This runs `eeg/feature_extraction.py`: load the BDF, keep scalp EEG channels (auxiliary and trigger channels
dropped), average re-reference, 1 to 40 Hz band-pass, then for each 10 s window compute the Welch power spectrum per
channel and average across channels. It writes `data/eeg_features/sub-01_ses-01.csv` with relative power in
delta (1-4 Hz), theta (4-8), alpha (8-13), beta (13-30), gamma (30-40) and `engagement_index = beta / (alpha + theta)`.

Useful options: `--window 10 --step 5`, `--channels Fz Cz Pz`, `--no-reref`. Run `python feature_extraction.py -h`
inside `eeg\` for all of them. A recording shorter than one window gives a clear error.

## 2. Replay in the backend

In `.env`:

```
EEG_MODE=DATASET_REPLAY
EEG_REPLAY_FILE=data/eeg_features/sub-01_ses-01.csv
EEG_TARGET_DEVICE=KH-S01
```

Restart the backend. The replay loops through the windows on a timer. The engagement index is converted to a 0..1
evidence value with a robust normalisation (median and MAD of the log index over the recording, then tanh), so the
value describes "high or low relative to this recording", not an absolute level.

## 3. How it enters the estimate

Evidence is used only for the real device named in `EEG_TARGET_DEVICE`. Simulated students never receive it. The fusion
step weights motion and EEG by how much the head is moving: while the head is moving, motion counts for more
(EEG channels pick up movement artefacts), while it is still, EEG counts for more. The weights are in `.env`
(`FUSION_*`). The device row shows the method as "Motion + EEG features" or "Motion only".

## 4. Other modes

- `EEG_MODE=OFF` (default): motion only.
- `EEG_MODE=PHYSICAL_EEG`: the backend accepts `POST /api/eeg/features` (delta, theta, alpha, beta, gamma) from a
  future driver and applies the same normalisation and fusion. No such driver exists in this prototype.
- `eeg/dataset_replay.py` prints a feature CSV as a live-looking table and can push it to the backend in
  `PHYSICAL_EEG` mode to exercise that endpoint. It is a preview tool.

## Limits

- One recording of one participant: it demonstrates plumbing, not validity.
- Band-power ratios such as beta / (alpha + theta) are used in the literature as engagement indices, but they are
  not a reliable measure of attention for an individual, especially with movement artefacts and consumer hardware.
- The replay is not synchronised with anything happening in the room.
