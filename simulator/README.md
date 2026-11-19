# Standalone student simulator

Simulated headbands (`SIM-01`, `SIM-02`, ...) that talk to a running backend over HTTP.

```
python student_simulator.py --url http://localhost:8000 --students 25 --duration 600 --flaky
```

Options: `--students 1..99`, `--duration` seconds (0 = until Ctrl+C), `--interval` telemetry seconds, `--heartbeat`,
`--flaky` (random disconnects), `--key` (if the backend has `DEVICE_API_KEY`), `--seed`.
Start a class on the dashboard first; the backend only records while a class is running. All data is labelled
Simulated. The dashboard's Demo and simulation page does the same thing inside the backend.
