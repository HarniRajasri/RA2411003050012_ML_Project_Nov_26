import { useState } from "react";
import { useNavigate } from "react-router-dom";
import EegPanel from "../components/EegPanel.jsx";
import { useLive } from "../components/LiveContext.jsx";
import { useToast } from "../components/Toast.jsx";
import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";

export default function DemoPage() {
  const toast = useToast();
  const nav = useNavigate();
  const { snapshot } = useLive();
  const { data: sim, reload } = useFetch(() => api.simStatus(), [], 2000);
  const [count, setCount] = useState(20);
  const [drop, setDrop] = useState(3);
  const [fraction, setFraction] = useState(50);
  const [busy, setBusy] = useState(false);

  const act = async (fn, msg) => {
    setBusy(true);
    try {
      const r = await fn();
      toast(typeof msg === "function" ? msg(r) : msg, "ok");
      reload();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };
  const classActive = !!snapshot?.class;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Demo and simulation</h1>
          <p>Only one physical headband exists, so the rest of the classroom is simulated in software. Simulated students go through the same backend logic as messages from a real headband and are always labelled SIM. Everything created here is synthetic: it demonstrates the software, not real students.</p>
        </div>
      </div>


      <div className="grid-eq">
        <section className="panel">
          <div className="panel-head"><h2>Simulated students</h2><span className="badge sim">{sim ? `${sim.sending} sending / ${sim.count}` : "-"}</span></div>
          <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {!classActive && <p className="note small">No class is running. Start one on the Dashboard first so the simulated students are recorded, or load the finished sample class below.</p>}
            <div className="btn-row">
              <label className="field" style={{ width: 110 }}>How many
                <input type="number" min={1} max={60} value={count} onChange={(e) => setCount(Number(e.target.value))} />
              </label>
              <button className="btn primary" style={{ alignSelf: "flex-end" }} disabled={busy} onClick={() => act(() => api.simAdd(count), (r) => `Added ${r.added.length} simulated students`)}>Add simulated students</button>
            </div>
            <div className="btn-row">
              <label className="field" style={{ width: 110 }}>Disconnect
                <input type="number" min={1} max={60} value={drop} onChange={(e) => setDrop(Number(e.target.value))} />
              </label>
              <button className="btn" style={{ alignSelf: "flex-end" }} disabled={busy} onClick={() => act(() => api.simDisconnectRandom(drop), (r) => `Disconnected ${r.disconnected.join(", ")}. They drop out after the device timeout.`)}>Disconnect random students</button>
              <button className="btn" style={{ alignSelf: "flex-end" }} disabled={busy} onClick={() => act(() => api.simReconnectAll(), (r) => `Reconnected ${r.reconnected.length} students`)}>Reconnect all</button>
            </div>
            <div>
              <div className="small muted" style={{ marginBottom: 6 }}>Class mood for a share of the simulated students</div>
              <div className="btn-row">
                <label className="field" style={{ width: 110 }}>Share (%)
                  <input type="number" min={0} max={100} value={fraction} onChange={(e) => setFraction(Number(e.target.value))} />
                </label>
                <button className="btn" style={{ alignSelf: "flex-end" }} disabled={busy} onClick={() => act(() => api.simScenario("drift_wave", fraction / 100), "Drift wave started: those students move a lot, so estimated engagement dips")}>Drift wave</button>
                <button className="btn" style={{ alignSelf: "flex-end" }} disabled={busy} onClick={() => act(() => api.simScenario("focus_wave", fraction / 100), "Focus wave started: those students stay still")}>Focus wave</button>
                <button className="btn" style={{ alignSelf: "flex-end" }} disabled={busy} onClick={() => act(() => api.simScenario("natural", 0), "Back to natural behaviour")}>Natural</button>
              </div>
              {sim && sim.scenario !== "natural" && <p className="small faint" style={{ marginTop: 6 }}>Active scenario: {sim.scenario.replace("_", " ")} on {sim.scenario_devices} students.</p>}
            </div>
            <div className="btn-row" style={{ borderTop: "1px solid var(--line)", paddingTop: 12 }}>
              <button className="btn" disabled={busy || !sim?.count} onClick={() => act(() => api.simClear(), (r) => `Stopped ${r.removed} simulated students`)}>Stop and remove all simulated students</button>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head"><h2>Sample class</h2></div>
          <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p>Creates one finished 60-minute class with 30 simulated students, late joiners, a disconnection and reconnection, and engagement that changes from window to window. It is labelled <b>DEMO / SIMULATED</b> everywhere.</p>
            <div className="btn-row">
              <button className="btn primary" disabled={busy} onClick={() => act(async () => { const r = await api.seedDemo(); nav(`/analytics/${r.class_id}`); return r; }, "Sample class added")}>Load sample class</button>
            </div>
          </div>
        </section>
      </div>

      <div className="grid-eq">
        <EegPanel eeg={snapshot?.eeg} />
        <section className="panel">
          <div className="panel-head"><h2>Suggested demo order (about 8 minutes)</h2></div>
          <div className="panel-body">
            <ol className="steps">
              <li>Power on the headband and confirm it appears on the Devices page.</li>
              <li>Start a class from the Dashboard (choose the 1-minute window for a short demo).</li>
              <li>Move your head with the real headband: watch the state change, then the red LED and vibration, then press the button to acknowledge.</li>
              <li>Add 20 to 30 simulated students and show the class filling up with the SIM badge.</li>
              <li>Disconnect a few students, then reconnect them. Point at the counters and the event feed.</li>
              <li>Start a drift wave for half the class and watch estimated engagement dip.</li>
              <li>End the class and open Analytics: interval chart, table, highest interval and connection timeline.</li>
              <li>Say clearly: these are estimates of class-level trends, the EEG part is a dataset replay, and nothing here proves attention.</li>
            </ol>
          </div>
        </section>
      </div>
    </main>
  );
}
