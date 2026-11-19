# EEG tools (offline)

```
pip install -r requirements.txt
python feature_extraction.py --input <file.bdf> --output ../data/eeg_features/sub-01_ses-01.csv
python dataset_replay.py --csv ../data/eeg_features/sub-01_ses-01.csv --step 1      # preview table
python -m pytest .                                                                  # feature tests
```

Default input: `EEG/Experiment2/sub-01_ses-01_task-stim01_eeg.bdf` in the project folder.
Full explanation and limits: [../docs/eeg.md](../docs/eeg.md). Output is EEG-derived features of a recorded dataset,
not live EEG.
