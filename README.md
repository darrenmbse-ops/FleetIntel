# FleetIntel: AI-Integrated Telemetry Pipeline

[cite_start]FleetIntel is an end-to-end IoT ecosystem that transforms raw vehicle data into natural language mechanical diagnostics[cite: 3]. [cite_start]Instead of just showing a dashboard of gauges, this system uses a "Detective" engine to analyze engine health in real-time, considering both internal sensor data and external environmental factors[cite: 4].

[📄 **View Technical Case Study (PDF)**](./docs/FleetIntel_%20AI-Integrated%20Telemetry%20Pipeline.pdf)

---

## 🚀 The Core Logic
[cite_start]FleetIntel moves beyond static "red-line" thresholds to provide intelligent alerting[cite: 6]:

* [cite_start]**Adaptive Baselines**: The system calculates $Z$-scores based on a vehicle’s historical performance to learn what "normal" looks like before flagging anomalies[cite: 8, 9].
* [cite_start]**Contextual Data Fusion**: By integrating the **Open-Meteo API**, the system pulls live weather and GPS elevation[cite: 10]. [cite_start]This allows the AI to distinguish between a mechanical cooling issue and a vehicle working hard to climb a steep hill in high heat[cite: 11].
* [cite_start]**Natural Language Reporting**: Raw PID codes are processed by **GPT-4o** to generate human-readable diagnoses sent directly to fleet managers via Telegram[cite: 12].

---

## 🛠 Tech Stack
* [cite_start]**Hardware**: Teltonika FMC003 (LTE Cat M1/NB-IoT) [cite: 14]
* [cite_start]**Ingestion**: Flespi (MQTT Broker / Protocol Gateway) [cite: 15]
* [cite_start]**Database**: PostgreSQL + TimescaleDB (Optimized for time-series telemetry) [cite: 16]
* [cite_start]**AI/Intelligence**: OpenAI API (GPT-4o), Open-Meteo API (Weather/Elevation Data) [cite: 16]
* [cite_start]**Backend**: Python 3.10+ (Pandas, Paho-MQTT, Psycopg2) [cite: 16]
* [cite_start]**Infrastructure**: Ubuntu Server managed with Systemd [cite: 17]

---

## 📂 Project Structure
* [cite_start]`src/logger.py`: Handles the MQTT stream from Flespi and maps raw JSON hex to the database[cite: 19].
* `src/detective.py`: The "Brain." [cite_start]Runs anomaly detection, fetches environmental context, and manages AI diagnostic flow[cite: 20, 21].
* [cite_start]`db/schema.sql`: The relational blueprints using an EAV model to handle OBDII PIDs without table migrations[cite: 22, 23].
* [cite_start]`.env.example`: A template for required API keys and database credentials.

---

## 🔧 Self-Healing & Integrity
[cite_start]To ensure production readiness, the Admin Telegram bot includes a `/status` command that audits[cite: 26]:
1. [cite_start]**Schema Integrity**: Verifies all required tables and columns[cite: 28].
2. [cite_start]**Service Health**: Checks background systemd services (Logger & Guardian)[cite: 29].
3. [cite_start]**Data Velocity**: Monitors pings received in the last 5 minutes[cite: 30].

---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.
