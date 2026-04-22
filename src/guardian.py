import os, time, json, pandas as pd, psycopg2, requests, subprocess
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global State
active_alerts = set()
last_update_id_admin = 0
last_maturation_ping = None

# Settings
YARIS_MIN_TEMP = 70  # Gatekeeper: Only analyze if engine is >= 70°C
ADMIN_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- HELPER FUNCTIONS ---

def get_external_context(lat, lon):
    """Fetches weather and elevation data for England (Open-Meteo, no key required)."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&elevation=true"
        resp = requests.get(url, timeout=5).json()
        ext_temp = resp.get("current_weather", {}).get("temperature")
        elevation = resp.get("elevation")
        return ext_temp, elevation
    except Exception as e:
        print(f"External API failed: {e}")
        return None, None

def get_service_status(service_name):
    """Checks if a systemd service is active on the server."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "active"
    except Exception: return False

def send_telegram_msg(token, chat_id, text, reply_markup=None):
    """Universal sender for Admin and Customers."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(url, data=payload, timeout=10)
    except Exception as e: print(f"Telegram post failed: {e}")

# --- BOT INTERACTION LOGIC ---

def check_customer_feedback(conn):
    """Processes 'Yes/No' button clicks from customers to train the AI."""
    cursor = conn.cursor()
    cursor.execute("SELECT fleet_bot_token, driver_telegram_id FROM customers WHERE is_active = True")
    for token, target_chat in cursor.fetchall():
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        try:
            resp = requests.get(url, timeout=5).json()
            for update in resp.get("result", []):
                if "callback_query" in update:
                    query = update["callback_query"]
                    if str(query.get("from", {}).get("id", "")) != str(target_chat): continue
                    data = query["data"]
                    if data.startswith("fb_"):
                        _, log_id, is_genuine = data.split("_")
                        cursor.execute("UPDATE anomaly_logs SET feedback = %s WHERE id = %s", (is_genuine == '1', log_id))
                        conn.commit()
                        msg = "✅ Recorded. We will monitor this closely." if is_genuine == '1' else "🔧 Understood. I've adjusted your vehicle's baseline to be less sensitive."
                        send_telegram_msg(token, target_chat, msg)
                        status = "REAL ISSUE" if is_genuine == '1' else "FALSE ALARM"
                        send_telegram_msg(ADMIN_TOKEN, ADMIN_CHAT_ID, f"📢 Customer {target_chat} flagged log {log_id} as: {status}")
        except: continue

def check_admin_commands(conn):
    """Handles Admin-only commands for system management."""
    global last_update_id_admin
    url = f"https://api.telegram.org/bot{ADMIN_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": last_update_id_admin + 1}, timeout=5).json()
        for update in resp.get("result", []):
            last_update_id_admin = update["update_id"]
            msg_obj = update.get("message", {})
            text = msg_obj.get("text", "")
            sender_id = str(msg_obj.get("chat", {}).get("id", ""))

            if sender_id != ADMIN_CHAT_ID: continue

            if text == "/status":
                cursor = conn.cursor()
                
                # --- INTEGRITY CODE ---
                tables_to_check = {
                    "obd2_logs": ["time", "device_id", "pid_name", "value"],
                    "customers": ["device_id", "customer_name", "driver_telegram_id", "fleet_bot_token", "is_active"],
                    "anomaly_logs": ["id", "device_id", "value", "diagnosis", "feedback"]
                }
                schema_errors = []
                for table, cols in tables_to_check.items():
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'")
                    actual = [row[0] for row in cursor.fetchall()]
                    missing = [c for c in cols if c not in actual]
                    if missing: schema_errors.append(f"{table} missing {missing}")
                
                script_errors = []
                for s in ["logger.py", "guardian.py"]:
                    if not os.path.exists(f"/home/darren/fleetintel/{s}"):
                        script_errors.append(f"{s} missing")

                env_keys = ["OPENAI_API_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
                env_errors = [k for k in env_keys if not os.getenv(k)]

                cursor.execute("SELECT count(*) FROM obd2_logs WHERE time > now() - interval '5 minutes'")
                recent = cursor.fetchone()[0]
                cursor.execute("""
                    SELECT 
                        COUNT(*) FILTER (WHERE first_ping <= now() - interval '31 days') as active_det,
                        COUNT(*) FILTER (WHERE first_ping > now() - interval '31 days') as learning
                    FROM (
                        SELECT c.device_id, MIN(l.time) as first_ping 
                        FROM customers c 
                        JOIN obd2_logs l ON c.device_id = l.device_id 
                        WHERE c.is_active = True 
                        GROUP BY c.device_id
                    ) as m
                """)
                res = cursor.fetchone()
                active_det, learning_det = res if res else (0, 0)
                
                logger_active = get_service_status("fleet-logger.service")
                guardian_active = get_service_status("guardian.service")

                integrity_pass = not (schema_errors or script_errors or env_errors)
                status_text = (
                    f"📊 *FLEETINTEL SYSTEM STATUS*\n\n"
                    f"{'✅' if integrity_pass else '⚠️'} *System Integrity:* {'Healthy' if integrity_pass else 'CONFLICT DETECTED'}\n"
                    f"{'└─ 📂 Schema: OK' if not schema_errors else '└─ 📂 Schema: ' + ', '.join(schema_errors)}\n"
                    f"{'└─ 📜 Scripts: OK' if not script_errors else '└─ 📜 Scripts: ' + ', '.join(script_errors)}\n\n"
                    f"{'✅' if logger_active else '❌'} *Logger:* {'Online' if logger_active else 'OFFLINE'} ({recent} pings/5m)\n"
                    f"{'✅' if guardian_active else '❌'} *Guardian:* {'Online' if guardian_active else 'OFFLINE'}\n"
                    f"🕵️ *Detective:* Running\n"
                    f"└─ 📡 *Active Monitoring:* {active_det} vehicles\n"
                    f"└─ 🎓 *Learning Mode:* {learning_det} vehicles\n"
                    f"⚠️ *Active Alerts:* {len(active_alerts)}"
                )
                send_telegram_msg(ADMIN_TOKEN, ADMIN_CHAT_ID, status_text)

            elif text.startswith("/add_client"):
                try:
                    parts = text.split(" ")
                    dev_id, cust_name, c_chat, c_tok, c_email = parts[1], parts[2], parts[3], parts[4], parts[5]
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO customers (device_id, customer_name, driver_telegram_id, fleet_bot_token, email_address)
                        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (device_id) DO UPDATE SET is_active = True;
                    """, (dev_id, cust_name, c_chat, c_tok, c_email))
                    conn.commit()
                    welcome_text = (
                        f"👋 *Hello {cust_name}!* \n\n"
                        f"You're all set! The AI is now in 'Learning Mode' for the next 30 days."
                    )
                    send_telegram_msg(c_tok, c_chat, welcome_text)
                    send_telegram_msg(ADMIN_TOKEN, ADMIN_CHAT_ID, f"✅ Client `{cust_name}` activated.")
                except Exception as e:
                    send_telegram_msg(ADMIN_TOKEN, ADMIN_CHAT_ID, f"❌ Error: {e}")
    except Exception as e: print(f"Admin Error: {e}")

# --- ANALYTICS ENGINE ---

def process_anomalies(device_id, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT driver_telegram_id, fleet_bot_token FROM customers WHERE device_id = %s AND is_active = True", (device_id,))
    res = cursor.fetchone()
    if not res: return 

    cust_chat, cust_bot = res
    query = "SELECT time, pid_name, value FROM obd2_logs WHERE device_id = %s ORDER BY time DESC LIMIT 200"
    df_long = pd.read_sql(query, conn, params=(device_id,))
    if df_long.empty: return
    
    lat = df_long[df_long['pid_name'] == 'GPS_LAT']['value'].iloc[0] if 'GPS_LAT' in df_long['pid_name'].values else None
    lon = df_long[df_long['pid_name'] == 'GPS_LON']['value'].iloc[0] if 'GPS_LON' in df_long['pid_name'].values else None
    
    ext_temp, elev = None, None
    if lat and lon:
        ext_temp, elev = get_external_context(lat, lon)

    df = df_long.pivot_table(index='time', columns='pid_name', values='value').sort_index(ascending=False)
    temp_col = next((c for c in df.columns if 'TEMP' in c.upper() or 'COOLANT' in c.upper()), None)
    if not temp_col or df[temp_col].iloc[0] < YARIS_MIN_TEMP: return

    cursor.execute("SELECT count(*) FROM anomaly_logs WHERE device_id = %s AND feedback = False", (device_id,))
    false_alarms = cursor.fetchone()[0]
    adaptive_threshold = 3.0 + (false_alarms * 0.5)
    
    latest_val = df[temp_col].iloc[0]
    mean, std = df[temp_col].mean(), df[temp_col].std()
    z_score = abs(latest_val - mean) / (std if std > 0 else 0.0001)

    if z_score > adaptive_threshold and device_id not in active_alerts:
        sensor_snapshot = df.iloc[0].to_dict()
        context_str = f"Outside Temp: {ext_temp}C, Elevation: {elev}m." if ext_temp else "Environmental context unavailable."
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a master mechanic. Explain the anomaly briefly using the sensor data and environmental context. Ask if they were driving hard or if it's a real issue."},
                {"role": "user", "content": f"Vehicle {device_id} (Z:{z_score:.1f}). Sensors: {sensor_snapshot}. Context: {context_str}"}
            ]
        )
        diagnosis = response.choices[0].message.content
        cursor.execute("INSERT INTO anomaly_logs (device_id, value, diagnosis) VALUES (%s, %s, %s) RETURNING id", (device_id, latest_val, diagnosis))
        log_id = cursor.fetchone()[0]
        conn.commit()
        buttons = {"inline_keyboard": [[
            {"text": "✅ Yes, real issue", "callback_data": f"fb_{log_id}_1"}, 
            {"text": "❌ No, car is fine", "callback_data": f"fb_{log_id}_0"}
        ]]}
        send_telegram_msg(cust_bot, cust_chat, f"🚨 *AI MECHANIC ALERT*\n\n{diagnosis}", reply_markup=buttons)
        active_alerts.add(device_id)
    elif z_score <= adaptive_threshold:
        active_alerts.discard(device_id)

# --- EXECUTION LOOP ---

def run_detective():
    global last_maturation_ping
    print("Detective Online (Environmental Context & Integrity Audit Enabled)...")
    iteration = 0
    while True:
        try:
            with psycopg2.connect(dbname="fleetintel", user="darren", host="/var/run/postgresql") as conn:
                if iteration % 10 == 0:
                    check_admin_commands(conn)
                    check_customer_feedback(conn)
                
                if iteration % 60 == 0:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT MIN(l.time) as first_ping, c.device_id, c.driver_telegram_id, c.fleet_bot_token 
                        FROM customers c
                        INNER JOIN obd2_logs l ON c.device_id = l.device_id
                        WHERE c.is_active = True 
                        GROUP BY c.device_id, c.driver_telegram_id, c.fleet_bot_token
                    """)
                    rows = cursor.fetchall()
                    
                    matured_today = []
                    for first_seen, dev_id, c_chat, c_tok in rows:
                        days_active = (datetime.now(first_seen.tzinfo) - first_seen).days
                        
                        if days_active == 31 and last_maturation_ping != datetime.now().date():
                            matured_today.append(dev_id)

                        if days_active >= 31:
                            process_anomalies(dev_id, conn)
                    
                    if matured_today:
                        send_telegram_msg(ADMIN_TOKEN, ADMIN_CHAT_ID, f"🎉 *DETECTIVE UPDATE:* Vehicles active 31 days: {', '.join(matured_today)}")
                        last_maturation_ping = datetime.now().date()

        except Exception as e: print(f"Loop error: {e}")
        iteration += 1
        time.sleep(1)

if __name__ == "__main__":
    run_detective()
