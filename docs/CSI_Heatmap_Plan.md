# Implementation Plan: CSI Sensing & Presence Automation

This document outlines the step-by-step implementation plan for integrating Wi-Fi Channel State Information (CSI) sensing into the `SmartElectric` project using the open-source **RuView** platform. By leveraging RuView's Edge AI, the architecture is kept lightweight and efficient.

## 1. Architecture Overview

*   **Hardware (ESP32-S3):** Acts as the CSI receiver. It captures Wi-Fi packets, runs a lightweight AI model on-device (Edge AI) to analyze the signal distortion, and determines presence/activity.
*   **Data Transfer (MQTT):** Because the AI runs directly on the ESP32-S3, it sends lightweight, actionable JSON payloads (e.g., `{"presence": true, "zone": "living_room"}`) over the existing MQTT broker, avoiding the need for high-bandwidth raw data streaming.
*   **Edge Backend (Python):** The existing `mqtt_worker.py` listens to the RuView MQTT topics and updates the local database.
*   **Automation:** The backend evaluates the presence state and triggers the SmartElectric relays accordingly.

---

## 2. Hardware Requirements

*   **Receiver (Rx):** **ESP32-S3** (Required for the DSP capabilities to run RuView's Edge AI).
*   **Transmitter (Tx):** A standard home Wi-Fi Router, or any standard ESP32 (such as existing smart plugs) that is constantly broadcasting data.

---

## 3. Firmware Setup

To create a robust mesh for the heatmap, you will use the new ESP32-S3 as the Receiver (Rx) and your existing classic ESP32 Smart Plug as the Transmitter (Tx).

### A. The Receiver: New ESP32-S3
RuView handles the extraction and parsing of raw CSI data natively on the device.

1.  **Install RuView:**
    *   Clone the RuView repository: `git clone https://github.com/ruvnet/RuView.git`
    *   Flash the RuView firmware onto your ESP32-S3.
2.  **Configuration:**
    *   Connect the ESP32-S3 to your Wi-Fi network.
    *   Configure RuView to point to your Edge Backend's MQTT broker (`MQTT_BROKER` IP and port).
    *   Provide the MAC addresses of your home Router and your existing ESP32 Smart Plug so RuView knows which Wi-Fi signals to monitor.

### B. The Transmitter: Existing ESP32 Smart Plug
To ensure the ESP32-S3 has enough signal data to analyze, the existing Smart Plug needs to consistently broadcast Wi-Fi packets.

1.  **Modify `esp32_smart_plug.ino`:**
    *   Add a simple periodic ping or increase the frequency of its MQTT payload updates. 
    *   If your smart plug currently only sends data every 10 seconds, it won't generate a "steady" tripwire. Modify the main `loop()` to send a lightweight heartbeat packet (or ping the router/ESP32-S3) at least 10 times a second (every 100ms) to ensure high-resolution sensing.

---

## 4. Edge Backend Updates (`edge/backend`)

The Edge Backend acts as a lightweight aggregator, ingesting the processed AI outputs directly via MQTT without needing to perform heavy digital signal processing.

1.  **Database Updates (`edge_db.py`):**
    *   Create a new table `presence_state`:
        ```sql
        CREATE TABLE presence_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT,
            is_present BOOLEAN,
            activity_level TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ```
2.  **MQTT Worker (`mqtt_worker.py`):**
    *   Subscribe to the new topic: `TOPIC_RUVIEW = "smartelectric/sensors/ruview"`.
    *   Add an `elif topic == TOPIC_RUVIEW:` block in the `on_message` callback.
    *   Parse the JSON payload from RuView and insert it into the `presence_state` table.
3.  **FastAPI Endpoints (`main.py`):**
    *   Add `GET /api/presence`: Returns the latest presence status for the frontend.

---

## 5. Calibration & Room Mapping

RuView features fast on-device learning for calibration and spatial mapping.

1.  **Baseline Calibration:** Turn on the ESP32-S3 in an empty room. RuView will establish the baseline CSI "fingerprint" of the static environment in about 30 seconds.
2.  **Presence Training:** Walk around specific zones (e.g., near the TV, near the Light) to allow the on-device AI to map signal distortions to physical locations.

---

## 6. SmartElectric Automation Integration

Link the clean presence data to the existing relay controls.

1.  **Trigger Rules Engine:**
    *   Modify the backend automation engine (e.g., in `main.py` or a dedicated loop) to check the `presence_state` table.
    *   **Rule Example:** `IF presence_state.is_present == True AND presence_state.zone == "TV_Area" THEN publish "ON" to TV relay.`
2.  **Cooldown Logic:**
    *   Implement a timeout (e.g., "Keep lights on for 5 minutes after presence is last detected") to prevent devices from rapidly toggling if someone briefly leaves the room or sits perfectly still.

---

## 7. Frontend / UI Development

1.  **Web Dashboard (`edge/frontend_static/index.html`):**
    *   Update the UI to show a "Live Presence" indicator.
    *   If using multiple ESP32-S3s for high resolution, create a simple CSS grid showing which sectors of the room are currently active based on the RuView MQTT feeds.

---

### Suggested Order of Execution

1. **Hardware:** Acquire an ESP32-S3 development board.
2. **Firmware:** Flash the RuView platform and connect it to the existing MQTT broker.
3. **Backend Integration:** Update `mqtt_worker.py` to log the RuView presence events.
4. **Automation:** Write the logic to turn the Smart Plugs on/off based on those events.
