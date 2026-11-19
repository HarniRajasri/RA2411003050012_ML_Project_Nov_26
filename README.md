# KHorizon — Smart Headband for Classroom Engagement Assistance

**Course:** 21CSC305P — Machine Learning  
**Academic Year:** 2026–2027  
**Repository:** `RA2411003050012_ML_Project_Nov_26`

## Team Details

| Role | Full Name | Register Number | Department | Section | Academic Year | GitHub |
|---|---|---|---|---|---|---|
| Team Leader | Harni Rajasri M D | RA2411003050012 | B.Tech CSE | A | 2026–27 | [@HarniRajasri](https://github.com/HarniRajasri) |
| Team Member | Kiruthika S | RA2411003050136 | B.Tech CSE | B | 2026–27 | [@Kiruthika-543](https://github.com/Kiruthika-543) |

## Mentor

**Dr. S. Kanaga Suba Raja**  
Head of the Department, Computer Science and Engineering

## Project Overview

KHorizon is a prototype classroom engagement and attention-awareness assistance system. It analyses head movement patterns from an MPU6050 inertial measurement unit (IMU), estimates possible attention drift over time, and can provide discreet vibration/LED feedback. A backend service and web dashboard support device telemetry, class sessions, event history and aggregate engagement trends.

The system estimates behavioural signals; it does **not** directly measure a student's mental attention, comprehension, or learning outcome.

## System Architecture

- **Wearable/firmware:** ESP32-WROOM-32 with MPU6050 accelerometer and gyroscope; Arduino C++ firmware.
- **Backend:** Python, FastAPI and SQLite (SQLAlchemy).
- **Frontend:** React and Vite dashboard.
- **Communication:** HTTP/JSON telemetry from the device; WebSocket updates to the dashboard.
- **Analytics:** Rule-based motion-state logic, temporal thresholds, weighted motion/optional EEG evidence fusion, smoothing and hysteresis.
- **EEG extension:** Offline feature extraction and dataset replay support are included; this is not equivalent to live EEG acquisition.

## Important Implementation Note

The current V1 should be described as a **rule-based motion analytics and sensor-fusion prototype**, not as a validated or trained machine-learning classifier. A supervised ML model may be developed in future after collecting appropriately consented and labelled data and evaluating it with participant-independent validation.

The repository may include simulator/demo components. Simulated devices and replayed EEG are for software demonstration and must not be presented as real participant measurements.

## Repository Structure

```text
esp32/       ESP32 firmware
backend/     FastAPI backend, analytics, database models and simulator
frontend/    React/Vite dashboard
eeg/         EEG preprocessing and feature extraction utilities
docs/        Project documentation and final report
```

## Setup (overview)

1. Install Python 3.10+ and Node.js (use versions compatible with the supplied dependency files).
2. Create a Python virtual environment and install backend dependencies from the backend requirements file.
3. Copy `.env.example` to `.env` and configure local values. Never commit `.env` or hardware Wi-Fi credentials.
4. Install frontend dependencies using the package manager and lockfile supplied in `frontend/`.
5. Configure the ESP32 Wi-Fi and backend endpoint in a local, untracked `esp32/KHorizon_Headband/secrets.h` file based on the supplied example/documentation, if required.
6. Run the backend and frontend using the project instructions in the repository documentation.

Consult the included README/DEMO documentation and backend/frontend subdirectories for exact commands and configuration.

## Project Report

The final report is available at [`docs/KHorizon_Final_Project_Report.pdf`](docs/KHorizon_Final_Project_Report.pdf).

## Privacy and Security

- Do not commit API keys, Wi-Fi passwords, `.env` files, private EEG/participant data, local databases, or generated credentials.
- Obtain appropriate consent and institutional approval before collecting student data.
- Treat engagement values as estimates, not diagnostic or definitive judgements about individuals.
- Review the security configuration before deploying beyond a trusted development network.

## License

This repository includes the MIT License in `LICENSE`. Review its terms and confirm that all third-party components and assets are compatible before public release.
