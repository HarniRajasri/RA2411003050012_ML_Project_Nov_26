# API reference

Base URL `http://<pc-ip>:8000`. Interactive documentation with try-it-out buttons is served at `/docs` (Swagger UI).
All bodies are JSON. Errors are `{"detail": "<readable message>"}` with status 401, 404, 409, 422, 503 or 500.
Times are ISO 8601 UTC (`2026-01-12T09:00:00.000Z`); the server clock is authoritative, so headbands do not send
timestamps.

If `DEVICE_API_KEY` is set in `.env`, the four `/api/device/*` endpoints require the header `X-KH-Key: <key>`.
Dashboard endpoints stay open.

## Device endpoints (used by the ESP32)

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/device/register` | `device_id`, optional `mac_address`, `firmware_version` | Idempotent. IDs starting `SIM-` are stored as SIMULATED, all others as REAL |
| POST | `/api/device/heartbeat` | `device_id`, optional `uptime_ms`, `rssi` (-120..0), `sensor_ok` | Returns `class_active`, `class_name`, `heartbeat_interval` |
| POST | `/api/device/telemetry` | `device_id`, `motion_score` (0..1), `motion_state`, `acceleration_magnitude`, `angular_velocity`, `orientation_change` | `motion_state` is `NORMAL`, `MOVING`, `POSSIBLE_ATTENTION_DRIFT` or `FEEDBACK`. Returns `stored:false` (not an error) when no class is running |
| POST | `/api/device/feedback` | `device_id`, `event` = `FEEDBACK_TRIGGERED` or `FEEDBACK_ACKNOWLEDGED`, optional `feedback_type` | Acknowledgements are matched to the latest open prompt |

`device_id`: 3 to 32 characters, letters, digits, `-` or `_`, starting with a letter or digit.
`mac_address`: `AA:BB:CC:DD:EE:FF`.

## Class endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/classes/start` | `{name, duration_minutes?, scheduled_end?, window_seconds? (10..3600)}`. 409 if a class is already active |
| POST | `/api/classes/end` | Closes the active class. 409 if none |
| GET | `/api/classes/current` | `{active, class}` |
| GET | `/api/classes` | All classes, newest first, with headband count and average estimated engagement |
| GET | `/api/classes/{id}` | One class |
| GET | `/api/classes/{id}/analytics?source=ALL\|REAL\|SIMULATED` | `summary`, `windows[]`, `peak`, `methodology` |
| GET | `/api/classes/{id}/timeline` | Per-device connection segments |
| GET | `/api/classes/{id}/events` | Connection events and the event log |

## Devices and system

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/devices` | All devices with status, source, last seen, estimate |
| GET, PATCH | `/api/devices/{id}` | Read, or set `{"student_label": "..."}` |
| GET | `/api/health` | Backend, database, WebSocket client count |
| GET | `/api/settings` | Non-secret configuration |
| GET | `/api/events?limit=` | Recent events |
| GET | `/api/live/history` | Live chart points for the running class |
| GET | `/api/eeg/status` | EEG mode, label, latest features and evidence |
| POST | `/api/eeg/features` | Push features from a physical EEG driver (only accepted when `EEG_MODE=PHYSICAL_EEG`, otherwise 409) |

## Simulation and demo

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/sim/add` | `{count}` new `SIM-xx` students |
| POST | `/api/sim/disconnect-random?count=N` | Silence N students (they time out like a real disconnect) |
| POST | `/api/sim/reconnect-all` | Resume all silenced students |
| POST | `/api/sim/{id}/disconnect`, `/reconnect` | One student |
| POST | `/api/sim/scenario` | `{scenario: natural\|drift_wave\|focus_wave, fraction: 0..1}` |
| POST | `/api/sim/clear` | Remove all simulated students |
| GET | `/api/sim/status` | Count, sending, scenario |
| POST | `/api/demo/seed` | Adds one finished 60-minute sample class labelled DEMO / SIMULATED |

## WebSocket `/ws/dashboard`

Server to client messages (JSON):

- `{"type":"hello", ...}` once on connect
- `{"type":"snapshot", "class", "metrics", "devices", "eeg", "live_point", "has_simulated"}` about once a second, and
  immediately after a change
- `{"type":"event", "event": {...}}` for each connection change, drift estimate, feedback or class event

The client may send the text `ping`; the server answers `{"type":"pong"}`.

## Examples (PowerShell)

```powershell
$h = @{ "Content-Type" = "application/json" }
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod -Method Post http://localhost:8000/api/classes/start -Headers $h -Body '{"name":"Physics","duration_minutes":50}'
Invoke-RestMethod -Method Post http://localhost:8000/api/device/heartbeat -Headers $h -Body '{"device_id":"KH-S01","rssi":-55}'
Invoke-RestMethod -Method Post http://localhost:8000/api/device/telemetry -Headers $h -Body '{"device_id":"KH-S01","motion_score":0.12,"motion_state":"NORMAL","acceleration_magnitude":1.0,"angular_velocity":0.1,"orientation_change":2}'
Invoke-RestMethod http://localhost:8000/api/classes/current
```
