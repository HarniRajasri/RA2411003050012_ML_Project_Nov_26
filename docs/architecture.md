# Architecture

```
ESP32 (core 1: sensing + state machine + LEDs)      Browser dashboard (React, HashRouter)
ESP32 (core 0: Wi-Fi + HTTP client)                        ^  WebSocket /ws/dashboard   |  REST /api/*
        | HTTP JSON                                          |                          v
        v                                          +--------------------- FastAPI app -----------------------+
  /api/device/*  ------------------------------->  |  api/*  ->  services/core.py (KHorizonCore)             |
                                                   |     connection state machine, snapshots, analytics      |
  sim/manager.py (in-process simulated students)-> |     analytics/fusion.py  analytics/windows.py  summary.py|
  eeg/manager.py (replay or push)  --------------> |     websocket/hub.py (publisher + monitor loops)        |
                                                   +---------------------------+-----------------------------+
                                                                               | SQLAlchemy
                                                                         SQLite (WAL) data/khorizon.db
```

## Backend layout

| Module | Responsibility |
|---|---|
| `main.py` | App factory, lifespan (background loops), CORS, error handlers, static dashboard |
| `config.py` | `.env` settings (secrets hidden from `/api/settings`) |
| `services/core.py` | The domain service every path goes through: class control, register, heartbeat, telemetry, feedback, timeout supervision, live snapshot, analytics cache |
| `analytics/fusion.py` | Motion (and optional EEG) evidence to estimated state, smoothing and hysteresis |
| `analytics/windows.py` | Interval aggregation, connection-interval reconstruction, highest interval |
| `analytics/summary.py` | Continuity counts, feedback counts, distributions |
| `sim/` | Behaviour model of restless / average / focused students and the manager that drives them |
| `eeg/` | Replay source, push source, normaliser, manager |
| `websocket/hub.py` | Client set, broadcast, snapshot publisher, heartbeat monitor |
| `services/demo_seed.py` | Builds the labelled sample class |

Simulated students call the same `KHorizonCore` methods as real HTTP requests, so the connection logic, storage and
analytics run the same code for both. They are stored with `source = SIMULATED` and the `SIM-` ID prefix.

## Connection state machine (per device)

```
            heartbeat / telemetry                  no message > 2 x HEARTBEAT_INTERVAL
DISCONNECTED ------------------> CONNECTED ----------------------------------------> RECONNECTING
      ^                              ^                                                     |
      |                              +------------- any message ---------------------------+
      +------------------ no message > DEVICE_TIMEOUT ------------------------------------+
```

`RECONNECTING` means late, not lost. Only a move to `DISCONNECTED` and back writes `DISCONNECTED` and `RECONNECTED`
connection events. Each device's class record keeps `first_connected_at`, `joined_late` (first seen after
`JOIN_GRACE_SECONDS`), `disconnect_count` and `reconnect_count`.

## Estimated state

1. The firmware reports a motion score and a motion state.
2. `fusion.py` maps the firmware state to evidence (`NORMAL` 0.85, `MOVING` 0.50, `POSSIBLE_ATTENTION_DRIFT` and
   `FEEDBACK` 0.15) and mixes it 70/30 with `1 - motion_score`. When EEG-derived evidence exists for that device it is
   blended in with weights that depend on movement (motion 0.75 / EEG 0.25 while moving, 0.30 / 0.70 while still).
3. An exponential moving average smooths the result and hysteresis (enter drift below 0.45, leave above 0.50)
   stops flicker.
4. Output: `ENGAGED` or `POSSIBLE_ATTENTION_DRIFT`, a score, and a **model confidence** (not certainty about the student).

## Analytics methodology

Implemented in `analytics/windows.py`; the same text is returned by the analytics endpoint and shown in the dashboard.

- Windows are `window_seconds` long from the class start (default 600). The last one may be partial; when a class is
  running, future windows show as upcoming.
- A device contributes to a window when it has at least `min_obs_per_window` (3) estimates in it. Its engaged
  fraction is `engaged estimates / all estimates`. The window's estimated engagement is the mean of these fractions.
- Estimated engaged students / possible drift students count devices with fraction at least / below 0.5.
- Connected students is the time-weighted average number of connected devices in the window, from connection events.
- Highest interval: maximum engagement, ties to the earliest, ignoring windows covering under half a window
  when full windows exist.
- Class summary counts: connected since start, disconnected at least once, joined after start, peak simultaneous connections.
- Running classes cache the analytics for 2 seconds; the windows are persisted to `engagement_windows` periodically
  and when the class ends.

## Database (SQLite, created automatically)

`classes`, `devices`, `class_devices`, `connection_events`, `telemetry`, `attention_events`, `feedback_events`,
`engagement_windows`, `event_log`. WAL mode is on so the dashboard can read while headbands write. Delete
`data/khorizon.db` (with the backend stopped) to start fresh.

## Real-time flow

Requests mark the core "dirty" and queue events. `publisher_loop` broadcasts queued events within 0.25 s and a
snapshot on change or every second. `monitor_loop` supervises heartbeats. The dashboard hook reconnects with
back-off, reloads recent history after a reconnect, and treats 8 s of silence as a dead socket.

## Security notes

Designed for a trusted classroom network. No user accounts. Optional `X-KH-Key` for headbands. Payloads are
validated (ranges, patterns, enums). Do not expose the port to the internet.
