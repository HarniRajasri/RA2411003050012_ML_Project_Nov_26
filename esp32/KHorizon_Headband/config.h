// KHorizon Headband - pins and tunable parameters. Nothing else in the sketch is hard-coded.
#pragma once

#define FIRMWARE_VERSION "1.0.0"

// ---------------- Pins (verified wiring) ----------------
#define PIN_SDA        21     // MPU6050 SDA
#define PIN_SCL        22     // MPU6050 SCL
#define PIN_VIBRATION  25     // vibration module IN (HIGH = on)
#define PIN_LED_GREEN  26     // status LED (through 1k resistor)
#define PIN_LED_RED    27     // feedback LED (through 1k resistor)
#define PIN_BUTTON     33     // push button to GND, INPUT_PULLUP (pressed = LOW)
// GPIO2 is intentionally unused.

#define MPU_ADDR       0x68

// ---------------- Timing ----------------
#define SAMPLE_PERIOD_MS        20      // 50 Hz motion sampling
#define TELEMETRY_INTERVAL_MS   2000    // periodic telemetry (also sent immediately on a state change)
#define TELEMETRY_MIN_GAP_MS    500
#define HEARTBEAT_INTERVAL_MS   5000    // default; the backend may override it in its replies
#define HTTP_TIMEOUT_MS         2500
#define WIFI_RETRY_MS           8000
#define SENSOR_RETRY_MS         2000

// ---------------- Motion score (0..1) ----------------
// instant = 0.5*gyro + 0.3*orientation change + 0.2*acceleration deviation, each normalised to 0..1
#define GYRO_FULL_SCALE_RAD_S   2.0f    // angular speed that counts as "full" movement
#define ORI_FULL_SCALE_DEG      30.0f   // posture change (vs slow baseline) that counts as "full"
#define ACC_FULL_SCALE_G        0.30f   // |acceleration| deviation from 1 g that counts as "full"
#define W_GYRO                  0.5f
#define W_ORI                   0.3f
#define W_ACC                   0.2f
#define SCORE_EMA_ALPHA         0.10f   // fast smoothing used by the state machine (per 20 ms sample)
#define BASELINE_ALPHA          0.001f  // slow posture baseline (about 20 s time constant)

// ---------------- Temporal state machine ----------------
#define MOVE_ENTER              0.35f   // matches MOTION_THRESHOLD in the backend .env
#define MOVE_EXIT               0.20f   // hysteresis: must fall below this to leave MOVING
#define MOVE_ENTER_MS           800     // movement must persist this long to count as MOVING
#define MOVE_EXIT_MS            1500    // and stillness must persist this long to return to NORMAL
#define DRIFT_EPISODES          3       // this many separate movement episodes ...
#define DRIFT_EPISODE_WINDOW_MS 60000   // ... within this window -> possible attention drift
#define DRIFT_SUSTAINED_MS      10000   // or continuous movement for this long
#define DRIFT_CONFIRM_MS        2000    // hold in POSSIBLE_ATTENTION_DRIFT before showing feedback
#define FEEDBACK_MAX_MS         20000   // feedback stops by itself after this long without a button press
#define FEEDBACK_PULSES         5       // vibration pulses (then the red LED keeps blinking silently)
#define VIB_ON_MS               250
#define VIB_PERIOD_MS           1000
#define COOLDOWN_MS             30000   // no new feedback for this long after feedback ends

// Feedback (red LED + vibration) only while the backend reports an active class.
// Set to 1 to test the headband on the bench without starting a class.
#define ALLOW_FEEDBACK_WITHOUT_CLASS 0

#define BUTTON_DEBOUNCE_MS      35
