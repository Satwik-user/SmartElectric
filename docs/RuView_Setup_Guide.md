# RuView Setup & Calibration Guide (ESP32-S3)

This guide provides a step-by-step workflow for initializing, flashing, and calibrating the ESP32-S3 with RuView before integrating it into the SmartElectric system.

---

## Phase 1: Hardware Preparation

1.  **Select the Right Board:** Ensure you have an **ESP32-S3** development board. Note your board's flash size (typically 4MB or 8MB) as you will need this when selecting the firmware.
2.  **Power & Cooling:** RuView performs intense Digital Signal Processing (DSP). If using a very small board (like the S3-Zero), ensure it is well-ventilated during setup. Use a high-quality USB data cable.
3.  **Find the Port:** Connect the ESP32-S3 to your computer.
    *   *Linux/Mac:* Run `ls /dev/tty*` to find the port (e.g., `/dev/ttyUSB0` or `/dev/cu.usbserial`).
    *   *Windows:* Check Device Manager for the COM port (e.g., `COM3`).

---

## Phase 2: Firmware Flashing

The easiest way to install RuView is using pre-compiled release binaries and `esptool`.

1.  **Install esptool:** 
    Open your terminal and run:
    ```bash
    pip install esptool
    ```
2.  **Download the Firmware:**
    *   Go to the [RuView GitHub Releases page](https://github.com/ruvnet/RuView/releases).
    *   Download the `.bin` firmware file that matches your chip (`esp32s3`) and memory size (e.g., 4MB or 8MB).
3.  **Erase the Flash (Crucial for stability):**
    Clear the board's memory before writing the new firmware to avoid partition errors:
    ```bash
    esptool.py --chip esp32s3 --port /dev/ttyUSB0 erase_flash
    ```
    *(Replace `/dev/ttyUSB0` with your actual port)*
4.  **Write the Firmware:**
    Flash the downloaded binary to the ESP32-S3:
    ```bash
    esptool.py --chip esp32s3 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 path/to/ruview_esp32s3_fw.bin
    ```

---

## Phase 3: Network & MQTT Provisioning

Once flashed, the ESP32-S3 needs to be connected to your local network and the SmartElectric backend.

1.  **Boot the Device:** Press the `RST` (Reset) button on the ESP32-S3.
2.  **Wi-Fi Onboarding:** 
    *   Upon first boot, the ESP32-S3 will likely broadcast its own Wi-Fi Access Point (e.g., `RuView-Setup`).
    *   Connect to this Wi-Fi network using your phone or laptop.
    *   A captive portal should appear (if not, navigate to `192.168.4.1` in your browser).
3.  **Enter Credentials:**
    *   Select your home Wi-Fi SSID and enter the password.
    *   **MQTT Configuration (HiveMQ Cloud):** In the setup portal, input your HiveMQ Cloud Cluster URL (e.g., `xxx.hivemq.cloud`) and set the port to `8883` for TLS connection. 
    *   Enter your HiveMQ username and password. 
    *   *(Note: If you are operating entirely offline, input your Edge Server's local IP address and port `1883` as a fallback.)*
    *   Set the Topic Prefix to `smartelectric/sensors/ruview`.
4.  **Reboot:** Save the settings. The ESP32-S3 will reboot and connect to your home router and the HiveMQ Cloud.

---

## Phase 4: Environmental Calibration (Baseline)

For RuView to detect presence accurately, it must first learn what an "empty" room looks like. This establishes the baseline CSI fingerprint.

1.  **Physical Placement:** Place the ESP32-S3 in its permanent location in the room. *Do not move it after this step.*
2.  **Clear the Room:** Ensure no humans or pets are in the room. Even minor movements (like a spinning fan) should ideally be in their normal state.
3.  **Initiate Calibration:**
    *   Depending on the RuView version, calibration either happens automatically on boot for the first 30 seconds, or it requires an MQTT trigger.
    *   If automatic: Simply walk out of the room for 1 minute after powering on the device.
    *   If manual: Publish a message to the RuView command topic (e.g., `smartelectric/sensors/ruview/cmd`) with the payload `{"cmd":"calibrate"}` while the room is empty.

---

## Phase 5: Verification & Testing

Before writing any automation logic, ensure the data is flowing into your backend correctly.

1.  **Listen to the Broker:**
    Use an MQTT client (like MQTT Explorer or `mosquitto_sub`) to connect to your HiveMQ Cloud cluster and subscribe to the feed:
    ```bash
    mosquitto_sub -h [YOUR_HIVEMQ_CLUSTER_URL] -p 8883 -u [USERNAME] -P [PASSWORD] -t "smartelectric/sensors/ruview/#" -v --capath /etc/ssl/certs/
    ```
2.  **Test Presence:**
    *   Walk into the room and move around. 
    *   You should see JSON payloads appearing in your terminal indicating a spike in activity or `presence: true`.
    *   Stand completely still for a few seconds. The payload should reflect a drop in macro-activity but still register presence (detecting micro-movements like breathing).
3.  **Test Absence:**
    *   Leave the room.
    *   Watch the terminal. Within 5-10 seconds, the payload should switch to `presence: false`.

Once Phase 5 is successful, your ESP32-S3 is fully calibrated and ready to be connected to the SmartElectric database!
