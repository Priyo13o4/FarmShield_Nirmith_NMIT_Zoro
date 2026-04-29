/* ============================================================
   FARMSHIELD - ESP32 Firmware
   Board:  ESP32 DevKit V1
   Tools→Board: "ESP32 Dev Module"   Upload speed: 115200
   ------------------------------------------------------------
   Libraries (Library Manager):
     - WiFi              (built-in)
     - PubSubClient      (Nick O'Leary)        v2.8+
     - DHT sensor library (Adafruit)           v1.4+
     - Adafruit Unified Sensor                 v1.1+
     - ArduinoJson       (Benoit Blanchon)     v6.21+
     - ModbusMaster      (4-20ma.com)          v2.0.1
   ============================================================ */

#include <ArduinoJson.h>
#include <DHT.h>
#include <HardwareSerial.h>
#include <ModbusMaster.h>
#include <PubSubClient.h>
#include <WiFi.h>

// ---------- USER CONFIG ----------
const char *WIFI_SSID = "BMV";
const char *WIFI_PASS = "Bmv123456";
const char *MQTT_HOST = "10.250.240.119"; // Raspberry Pi LAN IP
const uint16_t MQTT_PORT = 1883;
const char *MQTT_USER = "farmshield";
const char *MQTT_PASS = "farmshield123";
const char *DEVICE_ID = "farmshield_node1";
// ---------------------------------

// Pin map
#define SOIL_PIN 34
#define TDS_PIN 35

#define RAIN_PIN 33
#define DHT_PIN 4
#define PIR_PIN 13
#define TCS_S0 5
#define TCS_S1 18
#define TCS_S2 19
#define TCS_S3 21
#define TCS_OUT 22
#define MAX485_RX 16
#define MAX485_TX 17
#define MAX485_DE 25
#define RELAY_PIN 26
#define BUZZER_PIN 27
#define LED_PIN 2

// DHT
DHT dht(DHT_PIN, DHT11);

// Modbus over RS-485
HardwareSerial mod(2);
ModbusMaster node;
void preTx() { digitalWrite(MAX485_DE, HIGH); }
void postTx() { digitalWrite(MAX485_DE, LOW); }

// MQTT / WiFi
WiFiClient espClient;
PubSubClient mqtt(espClient);

// Calibration constants (TUNE for your hardware)
const float VREF = 3.3;
const int ADC_RES = 4095;
float SOIL_DRY_RAW = 3000; // ADC reading in air
float SOIL_WET_RAW = 1200; // ADC reading in water


// Thresholds (tune to crop)
float TH_SOIL_LOW = 30.0; // %  -> below = irrigate
float TH_SOIL_OK = 60.0;  // %  -> above = stop
float TH_TEMP_HIGH = 38.0;

float TH_TDS_HI = 1500.0;
int TH_RAIN_DRY = 2500; // higher = wetter (analog)

// State
bool autoMode = true;
bool pumpState = false;
bool buzzerForce = false;
unsigned long lastPub = 0;
const unsigned long PUB_MS = 5000;

// ==================================================================
void setupWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    delay(400);
    Serial.print(".");
  }
  digitalWrite(LED_PIN, HIGH);
  Serial.print(" OK  IP=");
  Serial.println(WiFi.localIP());
}

void mqttCallback(char *topic, byte *payload, unsigned int len) {
  String msg;
  msg.reserve(len);
  for (unsigned int i = 0; i < len; i++)
    msg += (char)payload[i];
  String t = String(topic);
  Serial.printf("MQTT< %s : %s\n", topic, msg.c_str());

  if (t == "farmshield/control/pump") {
    if (msg.equalsIgnoreCase("ON")) {
      pumpState = true;
      digitalWrite(RELAY_PIN, HIGH);
    }
    if (msg.equalsIgnoreCase("OFF")) {
      pumpState = false;
      digitalWrite(RELAY_PIN, LOW);
    }
  } else if (t == "farmshield/control/mode") {
    autoMode = msg.equalsIgnoreCase("AUTO");
  } else if (t == "farmshield/control/buzzer") {
    buzzerForce = msg.equalsIgnoreCase("ON");
    digitalWrite(BUZZER_PIN, buzzerForce ? HIGH : LOW);
  }
}

void mqttConnect() {
  while (!mqtt.connected()) {
    Serial.print("MQTT connecting... ");
    if (mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASS)) {
      Serial.println("OK");
      mqtt.subscribe("farmshield/control/pump");
      mqtt.subscribe("farmshield/control/mode");
      mqtt.subscribe("farmshield/control/buzzer");
    } else {
      Serial.printf("rc=%d retry in 3s\n", mqtt.state());
      delay(3000);
    }
  }
}

// ---- Sensor reads ----
float readSoilPct() {
  long s = 0;
  for (int i = 0; i < 10; i++) {
    s += analogRead(SOIL_PIN);
    delay(2);
  }
  float raw = s / 10.0;
  float pct = (SOIL_DRY_RAW - raw) * 100.0 / (SOIL_DRY_RAW - SOIL_WET_RAW);
  if (pct < 0)
    pct = 0;
  if (pct > 100)
    pct = 100;
  return pct;
}

float readTDS(float tempC) {
  long s = 0;
  for (int i = 0; i < 30; i++) {
    s += analogRead(TDS_PIN);
    delay(2);
  }
  float v = (s / 30.0) * VREF / ADC_RES;
  float comp = 1.0 + 0.02 * (tempC - 25.0);
  float vc = v / comp;
  return (133.42 * vc * vc * vc - 255.86 * vc * vc + 857.39 * vc) * 0.5;
}



int readRain() { return 4095 - analogRead(RAIN_PIN); } // ~0 dry, ~4095 wet
bool readMotion() { return digitalRead(PIR_PIN) == HIGH; }

void readColor(int &r, int &g, int &b) {
  // 20% scaling = S0 HIGH, S1 LOW (already set in setup)
  digitalWrite(TCS_S2, LOW);
  digitalWrite(TCS_S3, LOW); // R
  r = pulseIn(TCS_OUT, LOW, 50000);
  digitalWrite(TCS_S2, HIGH);
  digitalWrite(TCS_S3, HIGH); // G
  g = pulseIn(TCS_OUT, LOW, 50000);
  digitalWrite(TCS_S2, LOW);
  digitalWrite(TCS_S3, HIGH); // B
  b = pulseIn(TCS_OUT, LOW, 50000);
}

bool readNPK(uint16_t &n, uint16_t &p, uint16_t &k) {
  // Most JXBS / generic NPK probes: slave 0x01, holding regs 0x001E..0x0020
  uint8_t res = node.readHoldingRegisters(0x001E, 3);
  if (res == node.ku8MBSuccess) {
    n = node.getResponseBuffer(0);
    p = node.getResponseBuffer(1);
    k = node.getResponseBuffer(2);
    return true;
  }
  return false;
}

// ==================================================================
void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(SOIL_PIN, INPUT);
  pinMode(TDS_PIN, INPUT);

  pinMode(RAIN_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(TCS_S0, OUTPUT);
  pinMode(TCS_S1, OUTPUT);
  pinMode(TCS_S2, OUTPUT);
  pinMode(TCS_S3, OUTPUT);
  pinMode(TCS_OUT, INPUT);
  digitalWrite(TCS_S0, HIGH);
  digitalWrite(TCS_S1, LOW); // 20% freq scaling
  pinMode(MAX485_DE, OUTPUT);
  digitalWrite(MAX485_DE, LOW);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); // ~0-3.3V

  dht.begin();

  mod.begin(9600, SERIAL_8N1, MAX485_RX, MAX485_TX);
  node.begin(1, mod); // slave id 1
  node.preTransmission(preTx);
  node.postTransmission(postTx);

  setupWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(640);
}

// ==================================================================
void loop() {
  if (WiFi.status() != WL_CONNECTED)
    setupWifi();
  if (!mqtt.connected())
    mqttConnect();
  mqtt.loop();

  if (millis() - lastPub < PUB_MS)
    return;
  lastPub = millis();

  // --- Read everything ---
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t))
    t = 0;
  if (isnan(h))
    h = 0;

  float soil = readSoilPct();
  float tds = readTDS(t > 0 ? t : 25.0);

  int rain = readRain();
  bool mot = readMotion();
  int r = 0, g = 0, b = 0;
  readColor(r, g, b);
  uint16_t N = 0, P = 0, K = 0;
  bool npkOk = readNPK(N, P, K);

  // --- Auto irrigation ---
  if (autoMode) {
    bool dry = soil < TH_SOIL_LOW;
    bool noRain = rain < TH_RAIN_DRY;
    bool wetEnough = soil > TH_SOIL_OK;
    if (dry && noRain && !pumpState) {
      pumpState = true;
      digitalWrite(RELAY_PIN, HIGH);
    } else if (wetEnough && pumpState) {
      pumpState = false;
      digitalWrite(RELAY_PIN, LOW);
    }
  }

  // --- Alerts ---
  String alertMsg = "";
  if (mot)
    alertMsg = "Intruder/motion detected";
  else if (t > TH_TEMP_HIGH)
    alertMsg = "High temperature";

  else if (tds > TH_TDS_HI)
    alertMsg = "Water TDS too high";

  if (!buzzerForce)
    digitalWrite(BUZZER_PIN, alertMsg != "" ? HIGH : LOW);

  // --- Publish JSON ---
  StaticJsonDocument<640> doc;
  doc["device"] = DEVICE_ID;
  doc["temperature"] = t;
  doc["humidity"] = h;
  doc["soil"] = soil;
  doc["tds"] = tds;

  doc["rain"] = rain;
  doc["motion"] = mot;
  JsonObject c = doc.createNestedObject("color");
  c["r"] = r;
  c["g"] = g;
  c["b"] = b;
  JsonObject n = doc.createNestedObject("npk");
  n["n"] = N;
  n["p"] = P;
  n["k"] = K;
  n["ok"] = npkOk;
  doc["pump"] = pumpState;
  doc["mode"] = autoMode ? "AUTO" : "MANUAL";
  doc["alert"] = alertMsg;
  doc["uptime_s"] = millis() / 1000;

  char buf[640];
  size_t len = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish("farmshield/data", buf, len);
  if (alertMsg != "")
    mqtt.publish("farmshield/alerts", alertMsg.c_str());

  Serial.printf(
      "T=%.1f H=%.0f Soil=%.1f%% TDS=%.0f Rain=%d Mot=%d Pump=%d %s\n",
      t, h, soil, tds, rain, mot, pumpState, alertMsg.c_str());
}