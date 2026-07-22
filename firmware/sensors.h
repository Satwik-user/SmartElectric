#ifndef SENSORS_H
#define SENSORS_H

/**
 * @brief Initializes the BME280 sensor and configures the ESP32 ADC.
 */
void initSensors();

/**
 * @brief Computes True RMS current (Amps) for a given SCT-013 current sensor pin.
 *
 * @param pin ESP32 analog pin connected to the SCT-013 bias circuit.
 * @return double Calculated RMS current in Amperes.
 */
double readCurrentRMS(int pin);

/**
 * @brief Reads temperature and humidity from the BME280 sensor.
 *
 * @param temperature Reference to store temperature (°C).
 * @param humidity Reference to store humidity (%).
 * @return true if the reading was successful.
 * @return false if the reading failed.
 */
bool readBME280(float &temperature, float &humidity);

/**
 * @brief Reads atmospheric pressure from the BME280 sensor.
 *
 * @return float Pressure in hPa.
 */
float readPressure();

#endif // SENSORS_H