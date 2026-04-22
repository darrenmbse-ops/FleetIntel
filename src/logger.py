import os
import json
import time
import psycopg2
import paho.mqtt.client as mqtt
from datetime import datetime
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "fleetintel",
    "user": "",
    "host": "/var/run/postgresql"
}
FLESPI_MQTT_HOST = "mqtt.flespi.io"
FLESPI_TOKEN = os.getenv("FLESPI_TOKEN")
# Subscribing to all device messages from your Flespi account
TOPIC = "flespi/message/gw/devices/+"

# --- UPDATED MAPPING BASED ON YOUR FLESPI JSON ---
# These keys now match exactly what you see in your Flespi Toolbox
MAP = {
    "can.engine.coolant.temperature": "COOLANT_TEMP",
    "can.engine.rpm": "ENGINE_RPM",
    "can.vehicle.speed": "VEHICLE_SPEED",
    "battery.voltage": "BATTERY_VOLT",
    "position.latitude": "GPS_LAT",
    "position.longitude": "GPS_LON"
}

def connect_db():
    """Initializes and returns a database connection."""
    while True:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Database Connected.")
            return conn
        except Exception as e:
            print(f"DB Error: {e}. Retrying in 5s...")
            time.sleep(5)

# Global connection objects
conn = connect_db()
cur = conn.cursor()

def on_message(client, userdata, msg):
    """Callback for MQTT messages."""
    global conn, cur
    try:
        data = json.loads(msg.payload)
        
        # --- ID SYNC LOGIC ---
        # We prioritize 'device.id' (e.g., 8041965) to match your Telegram add_client setup.
        # It falls back to 'ident' (IMEI) if device.id is missing.
        device_id = data.get("device.id") or data.get("ident")
        
        if not device_id:
            return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing Data for ID: {device_id}")

        data_was_inserted = False

        for key, value in data.items():
            # Only process numeric metrics that exist in our MAP
            if isinstance(value, (int, float)):
                pid_name = MAP.get(key)
                
                # If the key is one we actually want to track
                if pid_name:
                    try:
                        cur.execute(
                            "INSERT INTO obd2_logs (time, device_id, pid_name, value) VALUES (NOW(), %s, %s, %s)",
                            (str(device_id), pid_name, value)
                        )
                        data_was_inserted = True
                    except (psycopg2.InterfaceError, psycopg2.OperationalError):
                        print("Connection lost. Reconnecting...")
                        conn = connect_db()
                        cur = conn.cursor()
                        # Retry the insert once after reconnecting
                        cur.execute(
                            "INSERT INTO obd2_logs (time, device_id, pid_name, value) VALUES (NOW(), %s, %s, %s)",
                            (str(device_id), pid_name, value)
                        )
                        data_was_inserted = True

        if data_was_inserted:
            conn.commit()
        
    except Exception as e:
        print(f"Processing Error: {e}")
        conn.rollback()

# --- MQTT INITIALIZATION ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(FLESPI_TOKEN)
client.on_message = on_message

def run_service():
    """Main execution loop with reconnect logic."""
    while True:
        try:
            print(f"Connecting to Flespi at {FLESPI_MQTT_HOST}...")
            client.connect(FLESPI_MQTT_HOST, 1883, 60)
            client.subscribe(TOPIC)
            print("Subscription Active. Monitoring incoming telemetry...")
            client.loop_forever()
        except Exception as e:
            print(f"MQTT Error: {e}. Restarting loop in 10s...")
            time.sleep(10)

if __name__ == "__main__":
    run_service()
