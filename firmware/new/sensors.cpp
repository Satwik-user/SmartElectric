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
    const int sampleCount = 400; 
    double sum = 0.0;
    double sumSq = 0.0;

    // 1. Take rapid samples over ~100ms (covers exactly five 50Hz cycles or six 60Hz cycles)
    for (int i = 0; i < sampleCount; i++) {
        int sample = analogRead(pin);
        
        sum += sample;
        sumSq += (double)sample * sample;
        
        // analogRead takes ~20us, + 230us delay = 250us per sample. 
        // 400 samples * 250us = 100,000us (100ms)
        delayMicroseconds(230); 
    }

    // 2. Calculate the Mean (this automatically finds the actual DC offset)
    double mean = sum / sampleCount;

    // 3. Calculate Variance: Average(x^2) - Average(x)^2
    double variance = (sumSq / sampleCount) - (mean * mean);
    
    // Prevent NaN from floating point inaccuracies on zero-current
    if (variance < 0) variance = 0.0; 

    // 4. Calculate RMS counts
    double rmsCounts = sqrt(variance);

    // 5. Convert to Voltage and then Amperes
    double rmsVoltage = rmsCounts * (3.3 / ADC_COUNTS);
    double currentAmps = rmsVoltage * SCT_CALIBRATION;

    // 6. Noise filter / Deadband
    if (currentAmps < 0.05) { 
        currentAmps = 0.0;
    }

    Serial.printf("Pin %d RMS current = %.3f A (Midpoint was %.1f)\n", pin, currentAmps, mean);

    return currentAmps;
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