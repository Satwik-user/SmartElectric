#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include "config.h"
#include "sensors.h"
#include <math.h>

Adafruit_BME280 bme;

void initSensors() {
    // Initialize BME280 sensor (try both common I2C addresses)
    if (!bme.begin(0x76)) {
        if (!bme.begin(0x77)) {
            Serial.println("Could not find BME280!");
            while (1);
        }
    }

    // Set ESP32 ADC resolution (12-bit)
    analogReadResolution(ADC_BITS);

    // Set ADC attenuation (0–3.3V range)
    analogSetAttenuation(ADC_11db);
}

double readCurrentRMS(int pin)
{
    int sample = analogRead(pin);

    Serial.print("Pin ");
    Serial.print(pin);
    Serial.print(" ADC = ");
    Serial.println(sample);

    delay(500);

    return 0.0;
}

bool readBME280(float &temperature, float &humidity) {
    temperature = bme.readTemperature();
    humidity = bme.readHumidity();

    if (isnan(temperature) || isnan(humidity)) {
        return false;
    }

    return true;
}

float readPressure() {
    return bme.readPressure() / 100.0F;
}