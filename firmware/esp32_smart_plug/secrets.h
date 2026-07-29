#ifndef SECRETS_H
#define SECRETS_H

// WiFi Configuration
#define WIFI_SSID "SmartElectric_WiFi"
#define WIFI_PASSWORD "SuperSecretWiFiPass"

// MQTT Configuration
// For HiveMQ Cloud: "your-cluster-id.s1.eu.hivemq.cloud"
// For Local Mosquitto: "192.168.1.100" or "localhost"
#define HIVEMQ_SERVER_HOST "your-cluster-id.s1.eu.hivemq.cloud"
#define LOCAL_MQTT_SERVER_IP "192.168.1.100"

// MQTT Authentication Credentials (Required for HiveMQ Cloud)
#define MQTT_USER "smartelectric_user"
#define MQTT_PASS "SmartElectricPass123"

#endif // SECRETS_H
