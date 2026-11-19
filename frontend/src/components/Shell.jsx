import { NavLink, Outlet } from "react-router-dom";
import Icon from "./Icon.jsx";
import { useLive } from "./LiveContext.jsx";
import { useNow } from "../hooks/useNow.js";
import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";

const NAV = [
  ["/", "Dashboard", "live"],
  ["/devices", "Devices", "devices"],
  ["/analytics", "Analytics", "analytics"],
  ["/history", "Class history", "history"],
  ["/demo", "Demo and simulation", "demo"],
  ["/system", "System", "system"],
];

function StatusStrip() {
  const { status, backendUp, snapshot } = useLive();
  const now = useNow(1000);
  const { data: health } = useFetch(() => api.health(), [backendUp], 10000);
  const eeg = snapshot?.eeg;

  const backend = backendUp === false ? ["bad", "Offline"] : backendUp ? ["ok", "Running"] : ["", "Checking"];
  const socket =
    status === "live" ? ["ok", "Live"] : status === "reconnecting" ? ["warn pulse", "Reconnecting"] : ["warn pulse", "Connecting"];
  const dbOk = health?.database === "READY";
  const eegLabel = !eeg ? "-" : eeg.mode === "OFF" ? "Off (motion only)" : eeg.mode === "DATASET_REPLAY" ? "Dataset replay" : "Physical EEG";

  return (
    <header className="topbar">
      <div className="status-item"><span className={`dot ${backend[0]}`} />Backend <b>{backend[1]}</b></div>
      <div className="status-item"><span className={`dot ${backendUp === false ? "bad" : dbOk ? "ok" : ""}`} />Database <b>{backendUp === false ? "Unknown" : dbOk ? "Ready" : "Checking"}</b></div>
      <div className="status-item"><span className={`dot ${socket[0]}`} />Live updates <b>{socket[1]}</b></div>
      <div className="status-item">
        <span className={`dot ${eeg && eeg.mode !== "OFF" && eeg.available ? "ok" : ""}`} />EEG input <b>{eegLabel}</b>
      </div>
      <div className="spacer" />
      <div className="status-item num">{new Date(now).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div>
    </header>
  );
}

function Banners() {
  const { snapshot, backendUp } = useLive();
  const simCount = snapshot?.metrics?.devices_online_sim ?? 0;
  const eeg = snapshot?.eeg;
  return (
    <>
      {backendUp === false && (
        <div className="banner down" role="alert">
          <b>Backend not reachable.</b> Start it with <span className="mono">scripts\start_backend.ps1</span> (Windows) or <span className="mono">./scripts/run_backend.sh</span>. This page reconnects by itself.
        </div>
      )}
      {snapshot?.has_simulated && (
        <div className="banner sim" role="note">
          <b>Simulation mode.</b> {simCount > 0 ? `${simCount} synthetic students are connected.` : "Simulated students exist in the data."} They are software-generated, not real hardware, and are labelled Simulated everywhere.
        </div>
      )}
      {eeg && eeg.mode === "DATASET_REPLAY" && (
        <div className="banner eeg" role="note">
          <b>EEG dataset replay (software-in-the-loop).</b> EEG-derived features come from a recorded public dataset and are applied to <span className="mono">{eeg.target_device}</span> only. This is not live EEG.
        </div>
      )}
    </>
  );
}

export default function Shell() {
  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <div className="brand-mark"><Icon name="headband" size={18} stroke={2.2} /></div>
          <div>
            <div className="brand-name">KHorizon</div>
            <div className="brand-sub">Smart Headband</div>
          </div>
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
              <Icon name={icon} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">Estimates of class-level trends, not measurements of individual attention.</div>
      </aside>
      <div className="main">
        <StatusStrip />
        <Banners />
        <Outlet />
      </div>
    </div>
  );
}
