-- Database Schema for FleetIntel

-- 1. Customers/Devices Table
CREATE TABLE customers (
    device_id VARCHAR(50) PRIMARY KEY,
    owner_name VARCHAR(100),
    telegram_chat_id BIGINT,
    car_model VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- 2. OBD2 Telemetry (TimescaleDB Hypertable)
CREATE TABLE obd2_logs (
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50),
    sensor_type VARCHAR(50),
    sensor_value DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

-- 3. AI Anomaly Logs
CREATE TABLE anomaly_logs (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ DEFAULT NOW(),
    device_id VARCHAR(50),
    diagnosis TEXT,
    severity_score FLOAT,
    weather_context JSONB
);

-- Convert obd2_logs to a hypertable for performance
SELECT create_hypertable('obd2_logs', 'time');
