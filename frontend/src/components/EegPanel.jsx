const BANDS = ["delta", "theta", "alpha", "beta", "gamma"];

export default function EegPanel({ eeg }) {
  if (!eeg) return null;
  const off = eeg.mode === "OFF";
  const max = eeg.bands ? Math.max(...BANDS.map((b) => eeg.bands[b]), 1e-9) : 1;
  return (
    <section className="panel" aria-label="EEG input">
      <div className="panel-head">
        <h2>EEG input</h2>
        <span className={`badge ${off ? "" : eeg.available ? "eeg" : "warn"}`}>
          {off ? "Off" : eeg.mode === "DATASET_REPLAY" ? "Dataset replay" : "Physical EEG"}
        </span>
      </div>
      <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <p className="small muted">{eeg.label}</p>
        {eeg.message && <p className="small faint">{eeg.message}</p>}
        {eeg.bands && (
          <>
            <div className="bars" aria-label="Relative band power of the replayed EEG window">
              {BANDS.map((b) => (
                <div className="row" key={b}>
                  <span>{b}</span>
                  <div className="track"><i style={{ width: `${(eeg.bands[b] / max) * 100}%` }} /></div>
                  <span className="num faint">{(eeg.bands[b] * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
            <dl className="kv small">
              <dt>Engagement index</dt><dd>{eeg.engagement_index}</dd>
              <dt>Evidence used in fusion</dt><dd>{eeg.evidence} (0 to 1)</dd>
              {eeg.condition && (<><dt>Recording</dt><dd>{eeg.condition}</dd></>)}
              <dt>Applied to</dt><dd>{eeg.target_device}</dd>
            </dl>
          </>
        )}
        <p className="small faint">EEG-derived features are extra evidence for one device. They are not proof of listening or comprehension.</p>
      </div>
    </section>
  );
}
