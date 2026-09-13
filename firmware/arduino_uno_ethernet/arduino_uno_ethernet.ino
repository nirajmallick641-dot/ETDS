#include <SPI.h>
#include <Ethernet.h>
#include <ArduinoJson.h>

// ETDS Arduino Uno + W5100/W5500 Ethernet Shield example.
// Replace sensor functions with your calibrated hardware readings.
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0x01 };
IPAddress fallbackIp(192, 168, 1, 177);

const char* API_HOST = "YOUR-RENDER-SERVICE.onrender.com";
const int API_PORT = 443; // HTTPS requires TLS-capable hardware/library; see README.
const char* API_PATH = "/api/hardware/telemetry";
const char* DEVICE_API_KEY = "CHANGE_ME_LONG_RANDOM_KEY";
const char* METER_ID = "MTR-001";
const float LATITUDE = 22.3072;
const float LONGITUDE = 73.1812;

float readVoltage() { return 240.0f; }          // Replace with sensor/meter reading
float readCurrent() { return 10.0f; }           // Replace with CT/Hall/meter reading
float readSourcePowerKw() { return NAN; }      // Replace if feeder sensor exists
bool readTamper() { return false; }             // Replace with tamper switch/flag

EthernetClient client;
unsigned long lastPost = 0;
const unsigned long POST_INTERVAL_MS = 5000;

void setupEthernet() {
  Serial.begin(9600);
  Ethernet.init(10);
  if (Ethernet.begin(mac) == 0) {
    Serial.println("DHCP failed; using fallback IP");
    Ethernet.begin(mac, fallbackIp);
  }
  delay(1000);
  Serial.print("IP: "); Serial.println(Ethernet.localIP());
}

void sendTelemetry() {
  float voltage = readVoltage();
  float current = readCurrent();
  float powerKw = voltage * current / 1000.0f;
  float sourceKw = readSourcePowerKw();
  bool tamper = readTamper();

  StaticJsonDocument<512> doc;
  doc["meter_id"] = METER_ID;
  doc["voltage"] = voltage;
  doc["current"] = current;
  doc["power_kw"] = powerKw;
  doc["tamper"] = tamper;
  doc["latitude"] = LATITUDE;
  doc["longitude"] = LONGITUDE;
  doc["relay_state"] = "on";
  doc["device_status"] = "online";
  if (!isnan(sourceKw)) {
    doc["source_power_kw"] = sourceKw;
    doc["load_power_kw"] = powerKw;
  }

  String body;
  serializeJson(doc, body);

  // IMPORTANT: plain EthernetClient is not HTTPS. Use a TLS-capable Ethernet
  // library/module or an HTTPS gateway before sending production credentials.
  if (!client.connect(API_HOST, 80)) {
    Serial.println("Connection failed");
    return;
  }
  client.println(String("POST ") + API_PATH + " HTTP/1.1");
  client.println(String("Host: ") + API_HOST);
  client.println("Content-Type: application/json");
  client.println(String("Authorization: Bearer ") + DEVICE_API_KEY);
  client.println(String("Content-Length: ") + body.length());
  client.println("Connection: close");
  client.println();
  client.print(body);

  unsigned long timeout = millis();
  while (client.connected() && millis() - timeout < 5000) {
    while (client.available()) {
      Serial.write(client.read());
      timeout = millis();
    }
  }
  client.stop();
  Serial.println();
}

void loop() {
  if (millis() - lastPost >= POST_INTERVAL_MS) {
    lastPost = millis();
    if (Ethernet.linkStatus() != LinkOFF) sendTelemetry();
  }
}
