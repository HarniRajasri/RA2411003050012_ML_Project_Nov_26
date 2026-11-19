/*
  KHorizon Smart Headband - firmware v1.0.0
  Board: ESP32 Dev Module (ESP32-WROOM-32)

  What it does
    - Reads an MPU6050 (I2C, GPIO21/22) at 50 Hz and turns head movement into a 0..1 motion score.
    - A temporal state machine classifies the wearer as NORMAL, MOVING, POSSIBLE_ATTENTION_DRIFT or FEEDBACK.
      This is an ESTIMATE from head movement only. It is not proof of attention and it is never a diagnosis.
    - Sends a heartbeat every few seconds and telemetry every 2 s (and immediately on a state change) to the
      KHorizon backend over Wi-Fi (HTTP + JSON).
    - On possible attention drift it shows gentle feedback: red LED + vibration pulses. The wearer presses the
      button (GPIO33) to acknowledge. Feedback ends by itself after FEEDBACK_MAX_MS.

  Design
    - Core 1 (Arduino loop): sensing, state machine, LEDs, vibration, button. Never blocked by the network.
    - Core 0 (network task): Wi-Fi reconnect, register, heartbeat, telemetry, feedback events, with retries.

  Green LED
    fast blink (0.2 s)      Wi-Fi not connected
    slow blink (1 s)        Wi-Fi OK, backend not reachable
    short flash every 2 s   connected, no class running
    solid on                connected and a class is running
  Both LEDs alternate quickly when the MPU6050 is not responding.

  Serial monitor (115200 baud) commands: s = status, f = test feedback, r = reset posture baseline.
*/
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <math.h>

#include "config.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Missing secrets.h. Copy secrets.h.example to secrets.h in this folder and fill in your Wi-Fi name, password and backend IP."
#endif
struct ImuSample;


// =====================================================================================================
// Shared state (written by one task, read by the other)
// =====================================================================================================
enum MotionState : uint8_t { ST_NORMAL = 0, ST_MOVING, ST_DRIFT, ST_FEEDBACK };
static const char *STATE_NAMES[] = {"NORMAL", "MOVING", "POSSIBLE_ATTENTION_DRIFT", "FEEDBACK"};

volatile bool     g_wifiUp = false;
volatile bool     g_backendOk = false;
volatile bool     g_classActive = false;
volatile bool     g_sensorOk = false;
volatile uint32_t g_hbIntervalMs = HEARTBEAT_INTERVAL_MS;

struct TelemetryMsg {
  char body[256];
};
struct FeedbackMsg {
  bool ack;
};
static QueueHandle_t g_telQ = nullptr;
static QueueHandle_t g_fbQ = nullptr;

static char g_deviceId[40];

// =====================================================================================================
// MPU6050 (raw register driver - no external library needed)
// =====================================================================================================
static bool mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

static bool mpuInit() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);  // WHO_AM_I
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)1) != 1) return false;
  uint8_t who = Wire.read();
  if (who != 0x68 && who != 0x70 && who != 0x71 && who != 0x72) {
    Serial.printf("[mpu] unexpected WHO_AM_I 0x%02X (continuing)\n", who);
  }
  bool ok = mpuWrite(0x6B, 0x00);   // wake up, internal oscillator
  delay(50);
  ok &= mpuWrite(0x1A, 0x03);       // DLPF ~44 Hz
  ok &= mpuWrite(0x1B, 0x08);       // gyro +-500 deg/s
  ok &= mpuWrite(0x1C, 0x08);       // accel +-4 g
  return ok;
}

struct ImuSample {
  float ax, ay, az;   // g
  float gx, gy, gz;   // rad/s
};

static bool mpuRead(ImuSample &s) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)14) != 14) return false;
  int16_t v[7];
  for (int i = 0; i < 7; i++) {
    uint8_t hi = Wire.read();
    uint8_t lo = Wire.read();
    v[i] = (int16_t)((hi << 8) | lo);
  }
  const float accScale = 8192.0f;                  // LSB/g at +-4 g
  const float gyroScale = 65.5f * 57.2957795f;     // LSB/(rad/s) at +-500 deg/s
  s.ax = v[0] / accScale;
  s.ay = v[1] / accScale;
  s.az = v[2] / accScale;
  s.gx = v[4] / gyroScale;
  s.gy = v[5] / gyroScale;
  s.gz = v[6] / gyroScale;
  return true;
}

// =====================================================================================================
// Motion processing
// =====================================================================================================
static float gyroBias[3] = {0, 0, 0};
static float basePitch = 0, baseRoll = 0;
static bool  baselineInit = false;

static float clamp01(float x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
static float angleDiff(float a, float b) {
  float d = a - b;
  while (d > 180.0f) d -= 360.0f;
  while (d < -180.0f) d += 360.0f;
  return d;
}

// Accumulates features between telemetry messages
struct Accum {
  float scoreSum = 0, accSum = 0, gyroSum = 0, oriMax = 0;
  uint16_t n = 0;
  void reset() { scoreSum = accSum = gyroSum = oriMax = 0; n = 0; }
} g_acc;

static float g_scoreFast = 0;   // EMA used by the state machine

static void calibrateGyro() {
  Serial.println("[mpu] calibrating gyro - keep the headband still for ~1 s");
  double sum[3] = {0, 0, 0};
  int got = 0;
  for (int i = 0; i < 100; i++) {
    ImuSample s;
    if (mpuRead(s)) {
      sum[0] += s.gx; sum[1] += s.gy; sum[2] += s.gz;
      got++;
    }
    delay(10);
  }
  if (got > 20) {
    for (int i = 0; i < 3; i++) gyroBias[i] = (float)(sum[i] / got);
  }
  baselineInit = false;
}

static void processSample(const ImuSample &s) {
  float gx = s.gx - gyroBias[0], gy = s.gy - gyroBias[1], gz = s.gz - gyroBias[2];
  float gyroMag = sqrtf(gx * gx + gy * gy + gz * gz);
  float accMag = sqrtf(s.ax * s.ax + s.ay * s.ay + s.az * s.az);

  float pitch = atan2f(-s.ax, sqrtf(s.ay * s.ay + s.az * s.az)) * 57.2957795f;
  float roll = atan2f(s.ay, s.az) * 57.2957795f;
  if (!baselineInit) {
    basePitch = pitch; baseRoll = roll; baselineInit = true;
  }
  float dp = angleDiff(pitch, basePitch), dr = angleDiff(roll, baseRoll);
  float oriChange = sqrtf(dp * dp + dr * dr);
  basePitch += BASELINE_ALPHA * dp;      // posture baseline drifts slowly toward the current posture
  baseRoll += BASELINE_ALPHA * dr;

  float gN = clamp01(gyroMag / GYRO_FULL_SCALE_RAD_S);
  float oN = clamp01(oriChange / ORI_FULL_SCALE_DEG);
  float aN = clamp01(fabsf(accMag - 1.0f) / ACC_FULL_SCALE_G);
  float inst = W_GYRO * gN + W_ORI * oN + W_ACC * aN;

  g_scoreFast += SCORE_EMA_ALPHA * (inst - g_scoreFast);

  g_acc.scoreSum += inst;
  g_acc.accSum += accMag;
  g_acc.gyroSum += gyroMag;
  if (oriChange > g_acc.oriMax) g_acc.oriMax = oriChange;
  g_acc.n++;
}

// =====================================================================================================
// State machine
// =====================================================================================================
static MotionState g_state = ST_NORMAL;
static uint32_t aboveSince = 0, belowSince = 0, movingSince = 0, driftSince = 0, feedbackSince = 0;
static uint32_t cooldownUntil = 0;
static uint32_t episodes[DRIFT_EPISODES];
static uint8_t  epHead = 0, epCount = 0;
static bool     g_stateChanged = false;

static void pushEpisode(uint32_t now) {
  episodes[epHead] = now;
  epHead = (epHead + 1) % DRIFT_EPISODES;
  if (epCount < DRIFT_EPISODES) epCount++;
}
static void clearEpisodes() { epCount = 0; epHead = 0; }
static bool episodesTriggered(uint32_t now) {
  if (epCount < DRIFT_EPISODES) return false;
  uint8_t oldest = (epHead + DRIFT_EPISODES - epCount) % DRIFT_EPISODES;   // oldest stored episode
  return (now - episodes[oldest]) <= DRIFT_EPISODE_WINDOW_MS;
}

static void setState(MotionState st) {
  if (st == g_state) return;
  Serial.printf("[state] %s -> %s (score %.2f)\n", STATE_NAMES[g_state], STATE_NAMES[st], g_scoreFast);
  g_state = st;
  g_stateChanged = true;
}

static bool feedbackAllowed() {
#if ALLOW_FEEDBACK_WITHOUT_CLASS
  return true;
#else
  return g_classActive;
#endif
}

static void enqueueFeedback(bool ack) {
  FeedbackMsg m{ack};
  if (xQueueSend(g_fbQ, &m, 0) != pdTRUE) {
    FeedbackMsg drop;
    xQueueReceive(g_fbQ, &drop, 0);
    xQueueSend(g_fbQ, &m, 0);
  }
}

static void startFeedback(uint32_t now) {
  if (!feedbackAllowed()) {
    // No class running: never disturb the wearer. Reset quietly.
    setState(ST_NORMAL);
    clearEpisodes();
    cooldownUntil = now + 10000;
    return;
  }
  setState(ST_FEEDBACK);
  feedbackSince = now;
  enqueueFeedback(false);
}

static void endFeedback(uint32_t now, bool acknowledged) {
  if (acknowledged) enqueueFeedback(true);
  clearEpisodes();
  aboveSince = belowSince = 0;
  cooldownUntil = now + COOLDOWN_MS;
  setState(ST_NORMAL);
}

static void updateStateMachine(uint32_t now) {
  float s = g_scoreFast;
  switch (g_state) {
    case ST_NORMAL:
      if (s >= MOVE_ENTER) {
        if (!aboveSince) aboveSince = now;
        if (now - aboveSince >= MOVE_ENTER_MS) {
          movingSince = now;
          belowSince = 0;
          pushEpisode(now);
          setState(ST_MOVING);
        }
      } else {
        aboveSince = 0;
      }
      break;

    case ST_MOVING:
      if (s < MOVE_EXIT) {
        if (!belowSince) belowSince = now;
        if (now - belowSince >= MOVE_EXIT_MS) {
          aboveSince = belowSince = 0;
          setState(ST_NORMAL);
          break;
        }
      } else {
        belowSince = 0;
      }
      if ((int32_t)(now - cooldownUntil) >= 0 &&
          (episodesTriggered(now) || (now - movingSince) >= DRIFT_SUSTAINED_MS)) {
        driftSince = now;
        setState(ST_DRIFT);
      }
      break;

    case ST_DRIFT:
      if (now - driftSince >= DRIFT_CONFIRM_MS) startFeedback(now);
      break;

    case ST_FEEDBACK:
      if (now - feedbackSince >= FEEDBACK_MAX_MS) endFeedback(now, false);   // expired, not acknowledged
      break;
  }
}

// =====================================================================================================
// Outputs (LEDs + vibration) and button
// =====================================================================================================
static bool sensorFaultBlink(uint32_t now) { return ((now / 150) % 2) == 0; }

static void updateOutputs(uint32_t now) {
  // ---- vibration + red LED
  bool vib = false, red = false;
  if (g_state == ST_FEEDBACK) {
    uint32_t t = now - feedbackSince;
    uint32_t pulse = t / VIB_PERIOD_MS;
    vib = (pulse < FEEDBACK_PULSES) && ((t % VIB_PERIOD_MS) < VIB_ON_MS);
    red = ((t % 600) < 350);            // steady-ish blinking until acknowledged
  }
  // ---- green LED (status)
  bool green;
  bool faultA = false, faultB = false;
  if (!g_sensorOk) {
    faultA = sensorFaultBlink(now);
    faultB = !faultA;
    green = faultA;
    red = faultB;
  } else if (!g_wifiUp) {
    green = ((now / 200) % 2) == 0;
  } else if (!g_backendOk) {
    green = ((now / 1000) % 2) == 0;
  } else if (!g_classActive) {
    green = (now % 2000) < 100;
  } else {
    green = true;
  }
  digitalWrite(PIN_VIBRATION, vib ? HIGH : LOW);
  digitalWrite(PIN_LED_RED, red ? HIGH : LOW);
  digitalWrite(PIN_LED_GREEN, green ? HIGH : LOW);
}

static bool     btnStable = HIGH, btnLast = HIGH;
static uint32_t btnChangedAt = 0;

static void pollButton(uint32_t now) {
  bool raw = digitalRead(PIN_BUTTON);
  if (raw != btnLast) {
    btnLast = raw;
    btnChangedAt = now;
  }
  if (raw != btnStable && (now - btnChangedAt) >= BUTTON_DEBOUNCE_MS) {
    btnStable = raw;
    if (btnStable == LOW) {                       // pressed
      Serial.println("[button] pressed");
      if (g_state == ST_FEEDBACK) endFeedback(now, true);
    }
  }
}

// =====================================================================================================
// Network task (core 0)
// =====================================================================================================
static bool jsonBool(const String &s, const char *key, bool &out) {
  String k = String("\"") + key + "\"";
  int i = s.indexOf(k);
  if (i < 0) return false;
  i = s.indexOf(':', i);
  if (i < 0) return false;
  i++;
  while (i < (int)s.length() && s[i] == ' ') i++;
  out = s.startsWith("true", i);
  return true;
}

static void handleReply(const String &body) {
  bool active;
  if (jsonBool(body, "class_active", active)) g_classActive = active;
  int i = body.indexOf("\"heartbeat_interval\"");
  if (i >= 0) {
    i = body.indexOf(':', i);
    if (i > 0) {
      float sec = body.substring(i + 1).toFloat();
      if (sec >= 2.0f && sec <= 30.0f) g_hbIntervalMs = (uint32_t)(sec * 1000.0f);
    }
  }
}

static bool postJson(const char *path, const char *body) {
  HTTPClient http;
  String url = String("http://") + BACKEND_HOST + ":" + String(BACKEND_PORT) + path;
  if (!http.begin(url)) return false;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  if (strlen(DEVICE_API_KEY) > 0) http.addHeader("X-KH-Key", DEVICE_API_KEY);
  int code = http.POST((uint8_t *)body, strlen(body));
  bool ok = code >= 200 && code < 300;
  if (ok) {
    handleReply(http.getString());
  } else if (code > 0) {
    Serial.printf("[net] %s -> HTTP %d %s\n", path, code, http.getString().c_str());
  }
  http.end();
  g_backendOk = ok || (code > 0 && code < 500);     // 4xx means the server is there but rejected the payload
  return ok;
}

static void ensureWifi() {
  static uint32_t lastTry = 0;
  bool up = WiFi.status() == WL_CONNECTED;
  if (up != g_wifiUp) {
    g_wifiUp = up;
    if (up) Serial.printf("[wifi] connected, IP %s, RSSI %d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    else Serial.println("[wifi] connection lost");
  }
  if (!up) {
    g_backendOk = false;
    uint32_t now = millis();
    if (lastTry == 0 || now - lastTry >= WIFI_RETRY_MS) {
      lastTry = now;
      Serial.printf("[wifi] connecting to %s ...\n", WIFI_SSID);
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  }
}

static bool doRegister() {
  char body[200];
  snprintf(body, sizeof(body), "{\"device_id\":\"%s\",\"mac_address\":\"%s\",\"firmware_version\":\"%s\"}", g_deviceId,
           WiFi.macAddress().c_str(), FIRMWARE_VERSION);
  bool ok = postJson("/api/device/register", body);
  Serial.printf("[net] register %s\n", ok ? "ok" : "failed (will retry)");
  return ok;
}

static bool doHeartbeat() {
  char body[160];
  int rssi = WiFi.RSSI();
  if (rssi > 0) rssi = 0;
  if (rssi < -120) rssi = -120;
  snprintf(body, sizeof(body), "{\"device_id\":\"%s\",\"uptime_ms\":%lu,\"rssi\":%d,\"sensor_ok\":%s}", g_deviceId,
           (unsigned long)millis(), rssi, g_sensorOk ? "true" : "false");
  return postJson("/api/device/heartbeat", body);
}

static bool sendFeedback(bool ack) {
  char body[160];
  snprintf(body, sizeof(body), "{\"device_id\":\"%s\",\"event\":\"%s\",\"feedback_type\":\"LED_VIBRATION\"}", g_deviceId,
           ack ? "FEEDBACK_ACKNOWLEDGED" : "FEEDBACK_TRIGGERED");
  for (int attempt = 0; attempt < 3; attempt++) {
    if (postJson("/api/device/feedback", body)) return true;
    vTaskDelay(pdMS_TO_TICKS(300));
  }
  Serial.println("[net] feedback event dropped after 3 attempts");
  return false;
}

static void networkTask(void *) {
  bool registered = false;
  uint32_t lastHb = 0;
  for (;;) {
    ensureWifi();
    if (g_wifiUp) {
      uint32_t now = millis();
      if (!registered) {
        registered = doRegister();
        lastHb = now;
        if (!registered) vTaskDelay(pdMS_TO_TICKS(2000));
      } else {
        FeedbackMsg fb;
        while (xQueueReceive(g_fbQ, &fb, 0) == pdTRUE) sendFeedback(fb.ack);

        if (now - lastHb >= g_hbIntervalMs) {
          lastHb = now;
          if (!doHeartbeat()) registered = false;    // re-register once the backend is back
        }
        TelemetryMsg tm;
        if (xQueueReceive(g_telQ, &tm, 0) == pdTRUE) {
          if (!postJson("/api/device/telemetry", tm.body)) registered = false;
        }
      }
    } else {
      registered = false;
      xQueueReset(g_telQ);           // stale telemetry is worthless after an outage
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// =====================================================================================================
// Telemetry scheduling (core 1)
// =====================================================================================================
static uint32_t lastTelemetry = 0;

static void maybeSendTelemetry(uint32_t now) {
  bool due = (now - lastTelemetry) >= TELEMETRY_INTERVAL_MS;
  bool event = g_stateChanged && (now - lastTelemetry) >= TELEMETRY_MIN_GAP_MS;
  if (!(due || event)) return;
  if (g_acc.n == 0 || !g_sensorOk) return;

  float n = (float)g_acc.n;
  float score = clamp01(g_acc.scoreSum / n);
  float acc = g_acc.accSum / n;
  float gyro = g_acc.gyroSum / n;
  float ori = g_acc.oriMax;
  if (acc > 50) acc = 50;
  if (gyro > 100) gyro = 100;
  if (ori > 360) ori = 360;

  TelemetryMsg m;
  snprintf(m.body, sizeof(m.body),
           "{\"device_id\":\"%s\",\"motion_score\":%.3f,\"motion_state\":\"%s\",\"acceleration_magnitude\":%.3f,"
           "\"angular_velocity\":%.3f,\"orientation_change\":%.2f}",
           g_deviceId, score, STATE_NAMES[g_state], acc, gyro, ori);
  if (xQueueSend(g_telQ, &m, 0) != pdTRUE) {           // queue full: drop the oldest, keep the newest
    TelemetryMsg drop;
    xQueueReceive(g_telQ, &drop, 0);
    xQueueSend(g_telQ, &m, 0);
  }
  g_acc.reset();
  g_stateChanged = false;
  lastTelemetry = now;
}

// =====================================================================================================
// Serial helper commands
// =====================================================================================================
static void printStatus() {
  Serial.printf("[status] id=%s state=%s score=%.2f wifi=%d backend=%d class=%d sensor=%d hb=%lums\n", g_deviceId,
                STATE_NAMES[g_state], g_scoreFast, (int)g_wifiUp, (int)g_backendOk, (int)g_classActive, (int)g_sensorOk,
                (unsigned long)g_hbIntervalMs);
}

static void handleSerial(uint32_t now) {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == 's') {
      printStatus();
    } else if (c == 'f') {
      Serial.println("[test] forcing feedback");
      if (g_state != ST_FEEDBACK) {
        feedbackSince = now;
        setState(ST_FEEDBACK);
        enqueueFeedback(false);
      }
    } else if (c == 'r') {
      baselineInit = false;
      Serial.println("[test] posture baseline reset");
    }
  }
}

// =====================================================================================================
// Arduino entry points
// =====================================================================================================
static uint32_t lastSample = 0, lastSensorRetry = 0, sensorFails = 0;

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("KHorizon Smart Headband firmware " FIRMWARE_VERSION);

  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_VIBRATION, OUTPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_VIBRATION, LOW);

  // Device identity: DEVICE_ID from secrets.h, or derived from the MAC address when left empty.
  if (strlen(DEVICE_ID) >= 3) {
    strncpy(g_deviceId, DEVICE_ID, sizeof(g_deviceId) - 1);
    g_deviceId[sizeof(g_deviceId) - 1] = 0;
  } else {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    snprintf(g_deviceId, sizeof(g_deviceId), "KH-%02X%02X%02X", mac[3], mac[4], mac[5]);
  }
  Serial.printf("Device ID: %s   MAC: %s\n", g_deviceId, WiFi.macAddress().c_str());

  // Lamp test: both LEDs and a short buzz so the wearer knows the board booted.
  digitalWrite(PIN_LED_GREEN, HIGH);
  digitalWrite(PIN_LED_RED, HIGH);
  digitalWrite(PIN_VIBRATION, HIGH);
  delay(250);
  digitalWrite(PIN_VIBRATION, LOW);
  delay(250);
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED, LOW);

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);
  Wire.setTimeOut(20);
  if (mpuInit()) {
    g_sensorOk = true;
    calibrateGyro();
    Serial.println("[mpu] MPU6050 ready");
  } else {
    g_sensorOk = false;
    Serial.println("[mpu] MPU6050 NOT found - check SDA=GPIO21, SCL=GPIO22, 3V3 and GND. Retrying in the background.");
  }

  g_telQ = xQueueCreate(6, sizeof(TelemetryMsg));
  g_fbQ = xQueueCreate(6, sizeof(FeedbackMsg));

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  xTaskCreatePinnedToCore(networkTask, "khnet", 8192, nullptr, 1, nullptr, 0);

  lastSample = millis();
  lastTelemetry = millis();
}

void loop() {
  uint32_t now = millis();
  handleSerial(now);

  if (now - lastSample >= SAMPLE_PERIOD_MS) {
    lastSample = (now - lastSample > 5 * SAMPLE_PERIOD_MS) ? now : lastSample + SAMPLE_PERIOD_MS;
    if (g_sensorOk) {
      ImuSample s;
      if (mpuRead(s)) {
        sensorFails = 0;
        processSample(s);
      } else if (++sensorFails >= 5) {
        g_sensorOk = false;
        Serial.println("[mpu] sensor stopped responding");
      }
    } else if (now - lastSensorRetry >= SENSOR_RETRY_MS) {
      lastSensorRetry = now;
      if (mpuInit()) {
        g_sensorOk = true;
        sensorFails = 0;
        calibrateGyro();
        Serial.println("[mpu] sensor recovered");
      }
    }
  }

  if (g_sensorOk) updateStateMachine(now);
  pollButton(now);
  updateOutputs(now);
  maybeSendTelemetry(now);
  delay(1);
}
