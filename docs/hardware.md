# Hardware and firmware

## Parts and wiring (verified)

ESP32 NodeMCU-style board (ESP32-WROOM-32, CP2102 USB).

| Part | Pin | ESP32 GPIO |
|---|---|---|
| MPU6050 SDA | SDA | 21 |
| MPU6050 SCL | SCL | 22 |
| MPU6050 power | VCC, GND | 3V3, GND (I2C address 0x68) |
| Vibration module | IN | 25 |
| Green LED (status) | anode via 1 kOhm | 26 |
| Red LED (feedback) | anode via 1 kOhm | 27 |
| Push button | one side | 33, other side to GND (internal pull-up, pressed = LOW) |
| Unused | | 2 |

All pin numbers and thresholds live in `esp32/KHorizon_Headband/config.h`.

## Install and upload

1. Arduino IDE 2.x with the **esp32 by Espressif Systems** board package (Boards Manager).
2. Board: **ESP32 Dev Module**. Choose the COM port of the CP2102. No extra libraries are required (the MPU6050 is
   read directly over I2C; networking uses the built-in `WiFi` and `HTTPClient`).
3. Copy `secrets.h.example` to `secrets.h` in the sketch folder and edit:
   - `WIFI_SSID`, `WIFI_PASSWORD`: a **2.4 GHz** network.
   - `BACKEND_HOST`: the PC's IPv4 address (`scripts\show_ip.ps1`). Not `localhost`.
   - `DEVICE_ID`: default `KH-S01`. Never start a real ID with `SIM-`.
   - `DEVICE_API_KEY`: only if you set one in the backend `.env`.
4. Upload, open the Serial Monitor at **115200 baud**.

The PC and the ESP32 must be on the same network, the backend must listen on `0.0.0.0` (the default), and Windows
Firewall must allow TCP 8000 on that network (`scripts\allow_firewall.ps1` as Administrator; set the Wi-Fi network
profile to *Private*).

## What the firmware does

- Samples the MPU6050 at 50 Hz and computes a 0..1 **motion score** from angular speed (50 %), posture change against
  a slow baseline (30 %) and acceleration deviation from 1 g (20 %).
- A state machine with hysteresis: `NORMAL`, `MOVING` (score at least 0.35 for 0.8 s; leaves below 0.20 for 1.5 s),
  `POSSIBLE_ATTENTION_DRIFT` (3 separate movement episodes within 60 s, or 10 s of continuous movement; held 2 s),
  then `FEEDBACK`.
- **Feedback**: red LED blinks and the vibration module pulses 5 times. Press the button (GPIO33) to acknowledge.
  If nobody presses it, feedback stops after 20 s. After feedback there is a 30 s cool-down.
- Feedback is shown only while the backend reports an active class. To test on the bench without a class, set
  `ALLOW_FEEDBACK_WITHOUT_CLASS` to `1` in `config.h`, or type `f` in the Serial Monitor.
- Sends a heartbeat every 5 s and telemetry every 2 s (and at once on a state change). Networking runs on its own
  core, retries automatically and re-registers when the backend returns.

## Green LED meanings

| Green LED | Meaning |
|---|---|
| fast blink | Wi-Fi not connected |
| slow blink (1 s) | Wi-Fi OK, backend unreachable |
| short flash every 2 s | connected, no class running |
| solid | connected and a class is running |
| green and red alternate quickly | the MPU6050 is not responding |

## Serial Monitor commands

`s` status, `f` force a feedback test, `r` reset the posture baseline. Keep the headband still for the first second
after power-up: the gyroscope is calibrated then.

## Tuning

Change values in `config.h` and re-upload. If normal fidgeting triggers feedback too easily, raise `MOVE_ENTER`,
raise `DRIFT_EPISODES` or lengthen `DRIFT_SUSTAINED_MS`. These defaults are reasonable starting points and have not
been validated against real classroom behaviour.

## Troubleshooting

- **Upload fails**: hold the BOOT button while "Connecting..." appears; check the COM port and a data-capable USB cable.
- **`MPU6050 NOT found`**: check SDA/SCL are not swapped and the module has 3V3 and GND.
- **Slow green blink forever**: wrong IP, firewall, Public network profile, or the backend is not running.
- **Device appears then goes Disconnected**: weak Wi-Fi or the PC went to sleep.
- **Compile error about `secrets.h`**: you have not copied `secrets.h.example` to `secrets.h`.
