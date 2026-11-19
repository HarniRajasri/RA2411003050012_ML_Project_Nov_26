import { useState } from "react";
import Dialog from "./Dialog.jsx";
import Icon from "./Icon.jsx";
import { useToast } from "./Toast.jsx";
import { api } from "../services/api.js";
import { clock, timeOf } from "../services/format.js";
import { useNow } from "../hooks/useNow.js";

const WINDOWS = [
  [600, "10 minutes (standard)"],
  [300, "5 minutes"],
  [60, "1 minute (short demo)"],
];

function defaultName() {
  return `Class ${new Date().toLocaleDateString([], { day: "2-digit", month: "short" })} ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export default function ClassControl({ cls }) {
  const toast = useToast();
  const now = useNow(1000);
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", duration: 50, window: 600 });

  const run = async (fn, ok) => {
    setBusy(true);
    try {
      await fn();
      toast(ok, "ok");
      setDialog(null);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  const start = () =>
    run(
      () => api.startClass({ name: form.name.trim() || defaultName(), duration_minutes: form.duration ? Number(form.duration) : null, window_seconds: Number(form.window) }),
      "Class started. Headbands that are online have joined."
    );
  const end = () => run(() => api.endClass(), "Class ended. Open Analytics to review it.");

  let elapsed = 0;
  let planned = 0;
  if (cls) {
    elapsed = Math.max(0, (now - new Date(cls.start_time).getTime()) / 1000);
    if (cls.scheduled_end) planned = (new Date(cls.scheduled_end).getTime() - new Date(cls.start_time).getTime()) / 1000;
  }

  return (
    <section className="panel">
      <div className="class-strip">
        {cls ? (
          <>
            <div>
              <div className="title">{cls.name}</div>
              <div className="small muted">Started {timeOf(cls.start_time, false)}{cls.scheduled_end ? `, scheduled to end ${timeOf(cls.scheduled_end, false)}` : ""}</div>
            </div>
            <div className="timer" aria-label="Elapsed time">{clock(elapsed)}</div>
            {planned > 0 && <div className="progress" aria-hidden="true"><i style={{ width: `${Math.min(100, (elapsed / planned) * 100)}%` }} /></div>}
            <div className="spacer" />
            <button className="btn danger" onClick={() => setDialog("end")}><Icon name="stop" size={14} />End class</button>
          </>
        ) : (
          <>
            <div>
              <div className="title">No class running</div>
              <div className="small muted">Start a class to begin recording estimates. Headbands that are already online join automatically.</div>
            </div>
            <div className="spacer" />
            <button className="btn primary" onClick={() => { setForm((f) => ({ ...f, name: defaultName() })); setDialog("start"); }}><Icon name="play" size={14} />Start class</button>
          </>
        )}
      </div>

      {dialog === "start" && (
        <Dialog title="Start class" onClose={() => setDialog(null)}>
          <div className="panel-body">
            <label className="field">Class name
              <input type="text" value={form.name} maxLength={120} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
            </label>
            <div className="split">
              <label className="field">Planned length (minutes)
                <input type="number" min={1} max={600} value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })} />
                <span className="hint">Optional. Used to show the empty windows still to come.</span>
              </label>
              <label className="field">Analytics window
                <select value={form.window} onChange={(e) => setForm({ ...form, window: e.target.value })}>
                  {WINDOWS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
            </div>
            <div className="btn-row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setDialog(null)}>Cancel</button>
              <button className="btn primary" onClick={start} disabled={busy}>Start class</button>
            </div>
          </div>
        </Dialog>
      )}
      {dialog === "end" && (
        <Dialog title="End this class?" onClose={() => setDialog(null)}>
          <div className="panel-body">
            <p>The class will be closed and its analytics saved. Headbands stay connected but stop being recorded.</p>
            <div className="btn-row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setDialog(null)}>Keep running</button>
              <button className="btn danger" onClick={end} disabled={busy}>End class</button>
            </div>
          </div>
        </Dialog>
      )}
    </section>
  );
}
