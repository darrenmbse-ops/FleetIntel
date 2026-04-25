# FleetIntel: AI-Integrated Telemetry Pipeline

FleetIntel is an end-to-end IoT ecosystem that transforms raw vehicle data into natural language mechanical diagnostics. Instead of just showing a dashboard of gauges, this system uses a "Detective" engine to analyze engine health in real-time, considering both internal sensor data and external environmental factors.

This architecture implements a hybrid 'Expert-Statistical' monitoring pipeline designed to eliminate the 'Learning Mode' cold-start problem common in purely data-driven telematics. By integrating SAE J1939 industrial thresholds as a primary safety net, the system provides immediate 'Day 1' protection against catastrophic mechanical failure while the 3-Sigma Z-Score 'Detective' engine matures its baseline for high-precision anomaly detection. To mitigate alert fatigue and increase diagnostic trust, every anomaly is contextualized via Environmental Data Fusion—mapping engine thermals against real-time ambient temperature and GPS-derived gradients from Open-Meteo to distinguish environmental load from genuine part failure. This modular approach, built on TimescaleDB Hypertables, ensures sub-second ingestion and query performance, making the system capable of scaling from a single vehicle to a full-scale defense or maritime fleet without sacrificing integrity or explainability

---

## 🚀 The Core Logic
FleetIntel moves beyond static "red-line" thresholds to provide intelligent alerting:

* **Adaptive Baselines**: The system calculates $Z$-scores based on a vehicle’s historical performance to learn what "normal" looks like before flagging anomalies.
* **Contextual Data Fusion**: By integrating environmental data, the system pulls live weather and GPS elevation. This allows the AI to distinguish between a mechanical cooling issue and a vehicle working hard to climb a steep hill in high heat.
* **Natural Language Reporting**: Raw PID codes are processed by GPT-4o to generate human-readable diagnoses sent directly to fleet managers via Telegram.

---

## 🛠 Tech Stack
* **Hardware**: Teltonika FMC003 (LTE Cat M1/NB-IoT)
* **Ingestion**: Flespi (MQTT Broker / Protocol Gateway)
* **Database**: PostgreSQL + TimescaleDB (Optimized for time-series telemetry)
* **AI/Intelligence**: OpenAI API (GPT-4o), Open-Meteo API (Weather/Elevation Data)
* **Backend**: Python 3.10+ (Pandas, Paho-MQTT, Psycopg2)
* **Infrastructure**: Ubuntu Server managed with Systemd

---

## 🔧 Self-Healing & Integrity
To ensure production readiness, the Admin Telegram bot includes a `/status` command that audits:
1. **Schema Integrity**: Verifies all required tables and columns.
2. **Service Health**: Checks background systemd services (Logger & Guardian).
3. **Data Velocity**: Monitors pings received in the last 5 minutes.




Code Access:
The core analytics engine (logger.py and detective.py) is maintained in a private repository for intellectual property protection. Access to the source code can be provided to potential partners or employers upon request. Please contact Darren for collaborator access.





---

## ⚖️ License
Distributed under the MIT License. See LICENSE file for more information.









