#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include "config.h"
#include "secrets.h"
#include "sensors.h"
#include "relays.h"

// Instantiate network clients
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Timing variables
unsigned long last_telemetry_time = 0;

void setup_wifi() {
    delay(10);
    Serial.println();
    Serial.print("Connecting to Wi-Fi SSID: ");
    Serial.println(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    randomSeed(micros());

    Serial.println("");
    Serial.println("Wi-Fi connected successfully!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
}

// MQTT callback to handle incoming command messages
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
    Serial.print("Message arrived on topic [");
    Serial.print(topic);
    Serial.println("] ");

    // Parse payload into JSON
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload, length);

    if (error) {
        Serial.print("JSON deserialization failed: ");
        Serial.println(error.c_str());
        return;
    }

    // Process relay control commands
    if (strcmp(topic, "smartelectric/control/relay") == 0) {
        const char* appliance = doc["appliance"];
        int state = doc["state"];

        if (appliance != NULL) {
            Serial.printf("Received relay control command: %s -> %d\n", appliance, state);
            
            // Execute state change with safety checks
            bool success = setRelayState(appliance, state);
            
            // Publish acknowledgement log back to broker
            StaticJsonDocument<256> logDoc;
            char logBuffer[256];
            
            if (success) {
                logDoc["level"] = "INFO";
                logDoc["message"] = String("Successfully set relay for ") + appliance + " to " + (state == 1 ? "ON" : "OFF");
            } else {
                logDoc["level"] = "WARNING";
                logDoc["message"] = String("Rejected relay command for ") + appliance + " (lockout active or invalid name)";
            }
            
            serializeJson(logDoc, logBuffer);
            mqttClient.publish("smartelectric/logs", logBuffer);
        }
    }
}

void reconnect_mqtt() {
    // Loop until we're reconnected
    while (!mqttClient.connected()) {
        Serial.print("Attempting MQTT connection...");
        // Create a unique client ID using ESP32 MAC address
        String clientId = "SmartElectric-ESP32-Client-";
        clientId += String(WiFi.macAddress());
        
        // Attempt to connect
        bool connected = false;
        if (strlen(MQTT_USER) > 0) {
            connected = mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASS);
        } else {
            connected = mqttClient.connect(clientId.c_str());
        }

        if (connected) {
            Serial.println("connected!");
            // Once connected, publish boot log
            StaticJsonDocument<128> bootDoc;
            bootDoc["level"] = "INFO";
            bootDoc["message"] = "ESP32 Firmware booted and connected to broker.";
            char bootBuffer[128];
            serializeJson(bootDoc, bootBuffer);
            mqttClient.publish("smartelectric/logs", bootBuffer);
            
            // Resubscribe to control topic
            mqttClient.subscribe("smartelectric/control/relay");
        } else {
            Serial.print("failed, rc=");
            Serial.print(mqttClient.state());
            Serial.println(" try again in 5 seconds");
            // Wait 5 seconds before retrying
            delay(5000);
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("SmartElectric ESP32 Firmware Starting...");

    // Initialize relays first (safety: force low state immediately)
    initRelays();

    // Initialize sensors
    initSensors();

    // Configure WiFi connection
    setup_wifi();

    // Configure MQTT Broker settings
    mqttClient.setServer(MQTT_SERVER_IP, MQTT_PORT);
    mqttClient.setCallback(mqtt_callback);
}

void loop() {
    // Ensure WiFi and MQTT connections are maintained
    if (WiFi.status() != WL_CONNECTED) {
        setup_wifi();
    }
    
    if (!mqttClient.connected()) {
        reconnect_mqtt();
    }
    
    mqttClient.loop();

    // Telemetry Publishing Loop (Non-blocking timer)
    unsigned long current_time = millis();
    if (current_time - last_telemetry_time >= TELEMETRY_INTERVAL_MS) {
        last_telemetry_time = current_time;

        // 1. Read SCT-013 current values
        double current_light = readCurrentRMS(SENSOR_LIGHT_PIN);
        double current_tv = readCurrentRMS(SENSOR_TV_PIN);
        double current_fridge = readCurrentRMS(SENSOR_FRIDGE_PIN);
        double current_fan = readCurrentRMS(SENSOR_FAN_PIN);

        // Construct current telemetry JSON payload
        StaticJsonDocument<256> currentDoc;
        currentDoc["Light"] = current_light;
        currentDoc["TV"] = current_tv;
        currentDoc["Fridge"] = current_fridge;
        currentDoc["Fan"] = current_fan;
        currentDoc["voltage"] = GRID_VOLTAGE;

        char currentBuffer[256];
        serializeJson(currentDoc, currentBuffer);
        mqttClient.publish("smartelectric/sensors/current", currentBuffer);

        // 2. Read DHT22 temperature and humidity values
        float temperature = 0.0;
        float humidity = 0.0;
        bool bme_success = readBME280(temperature, humidity);

        if (bme_success) {
    StaticJsonDocument<128> bmeDoc;
    bmeDoc["temperature"] = temperature;
    bmeDoc["humidity"] = humidity;
    bmeDoc["pressure"] = readPressure();

    char bmeBuffer[128];
    serializeJson(bmeDoc, bmeBuffer);
    mqttClient.publish("smartelectric/sensors/bme280", bmeBuffer);

} else {
    StaticJsonDocument<128> errDoc;
    errDoc["level"] = "WARNING";
    errDoc["message"] = "BME280 read failure.";

    char errBuffer[128];
    serializeJson(errDoc, errBuffer);
    mqttClient.publish("smartelectric/logs", errBuffer);

    Serial.println("BME280 Sensor reading failed!");
}
        
        // Output debug to serial console
        Serial.printf("Telemetry Sent - Current (A) -> Light: %.3f, TV: %.3f, Fridge: %.3f, Fan: %.3f. DHT -> Temp: %.1f C, Hum: %.1f%%\n",
                      current_light, current_tv, current_fridge, current_fan, temperature, humidity);
    }
}