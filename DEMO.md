# Demo guide (about 8 minutes)

Aim: show the working system honestly. One real headband plus a simulated classroom, with the estimates clearly
described as class-level trends.

## Before the demo (10 minutes earlier)

1. Start the backend: `.\scripts\start_backend.ps1`. Open `http://localhost:8000`.
2. Power on the headband. Green LED: short flash every 2 s means connected with no class. It should appear on **Devices**.
3. Optional EEG: `EEG_MODE=DATASET_REPLAY` in `.env` and the feature CSV extracted (see `docs/eeg.md`). The top bar should
   say *EEG input: Dataset replay*.
4. Click **Load sample class** on the Demo page once, so you have a finished class to fall back on.
5. Close other class runs so the Dashboard shows *No class running*.

## Script

| Step | Do | Say |
|---|---|---|
| 1. The idea | Show the headband | "It measures head movement only. From that we estimate class-level engagement. It does not read brain activity." |
| 2. Start | Dashboard, **Start class**, choose the 1-minute window | "Headbands that are online join automatically. The green LED goes solid." |
| 3. Real device | Move your head for several seconds, repeatedly | "Movement patterns raise a possible attention drift estimate. The red LED and vibration are a gentle prompt." Press the button. "Acknowledgement shows in the event feed." |
| 4. Classroom | **Demo and simulation**, add 25 simulated students | "Only one headband exists, so the rest are simulated. They are labelled SIM and the banner says simulation mode." |
| 5. Reliability | Disconnect 3 random students, wait 15 s, reconnect all | "Disconnected and reconnected are tracked separately. Connected-since-start, disconnected-at-least-once and joined-after-start are three different counts." |
| 6. Class mood | Drift wave for 60 %, then Focus wave | "Estimated engagement dips and recovers. The interval bars update every window." |
| 7. EEG | Point at the EEG panel | "This is dataset replay: features from a recorded public dataset applied to the one real device. A physical EEG sensor would plug into the same interface later." |
| 8. End | **End class**, open **Analytics** | "Interval chart and table, the highest-engagement interval, and the connection timeline." Use the source filter to show real-only vs simulated. |
| 9. Close | System page | "These are estimates for class-level trends. They do not prove attention, comprehension or anything about one student." |

## If something goes wrong

- **Headband missing from Devices**: check the green LED (see `docs/hardware.md`), the IP in `secrets.h`, the firewall
  script. Continue with the simulation and say so.
- **Nothing shows at all**: open **Class history** and use the sample class; it needs no hardware.
- **Backend window closed**: rerun `start_backend.ps1`; the dashboard reconnects by itself and data is kept.

## Likely questions

- *Is this accurate?* Not validated. Thresholds are reasonable defaults; a study comparing estimates with observed
  behaviour would be the next step.
- *Why not EEG on every student?* One physical device exists; EEG hardware is costly and needs care with movement artefacts.
- *Privacy?* Local database, device IDs not names, movement features only, no audio or video.
