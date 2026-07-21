#ifndef CONFIG_H
#define CONFIG_H

// Network configurations
#define MQTT_PORT 1883
extern const char* mqtt_server; // Defined in secrets.h / config.cpp if overridden

// DHT22 Configuration
#define DHT_PIN 4
#define DHT_TYPE DHT22

// Relay Pin Mappings
#define RELAY_LIGHT_PIN 18
#define RELAY_TV_PIN    19
#define RELAY_FRIDGE_PIN 21
#define RELAY_FAN_PIN    22

// SCT-013 Current Sensor Analog Input Pins (ESP32 ADC pins)
#define SENSOR_LIGHT_PIN 32
#define SENSOR_TV_PIN    33
#define SENSOR_FRIDGE_PIN 34
#define SENSOR_FAN_PIN    35

// AC Electrical Constants (Indian standard grid)
#define GRID_VOLTAGE 230.0    // Nominal RMS Voltage (V)
#define GRID_FREQUENCY 50.0   // AC Frequency (Hz)

// SCT-013 Calibration Factor (Current Calibration value)
// For 100A/50mA sensor with 20-ohm burden resistor on ESP32 (3.3V ADC limit)
// Math: (100A / 0.05A) / BurdenResistor_20_ohms = 100
#define SCT_CALIBRATION 100.0

// ADC Configuration for ESP32
#define ADC_BITS 12
#define ADC_COUNTS 4096

// Loop & Reporting Intervals
#define TELEMETRY_INTERVAL_MS 5000  // Send telemetry every 5 seconds
#define SAFETY_LOCKOUT_MS     3000  // Prevent relay chattering (min 3 seconds between state changes)

#endif // CONFIG_H
