-- This schema defines the table for storing proxy performance metrics.
-- Run this script against your database, e.g.:
-- psql -U your_user -d your_db -f schema.sql

-- Drop the table if it already exists to ensure a clean setup
DROP TABLE IF EXISTS proxy_logs;

-- Create the main logging table
CREATE TABLE proxy_logs (
    log_id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    client_address VARCHAR(255) NOT NULL,
    destination_address VARCHAR(255) NOT NULL,
    destination_port INT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    connection_duration_ms INT,
    throughput_kbps NUMERIC(10, 2),
    status VARCHAR(50) DEFAULT 'active', -- e.g., 'active', 'closed', 'error'
    error_message TEXT
);

-- Add indexes for faster querying on commonly filtered columns
CREATE INDEX idx_start_time ON proxy_logs(start_time);
CREATE INDEX idx_client_address ON proxy_logs(client_address);
CREATE INDEX idx_destination_address ON proxy_logs(destination_address);

-- Add comments to explain the purpose of each column
COMMENT ON COLUMN proxy_logs.log_id IS 'Unique identifier for each log entry.';
COMMENT ON COLUMN proxy_logs.session_id IS 'Unique ID for a single proxy session/connection.';
COMMENT ON COLUMN proxy_logs.client_address IS 'The IP address and port of the client connecting to the proxy.';
COMMENT ON COLUMN proxy_logs.destination_address IS 'The target address (IP or domain) the client wants to connect to.';
COMMENT ON COLUMN proxy_logs.destination_port IS 'The target port.';
COMMENT ON COLUMN proxy_logs.start_time IS 'Timestamp when the connection was initiated.';
COMMENT ON COLUMN proxy_logs.end_time IS 'Timestamp when the connection was terminated.';
COMMENT ON COLUMN proxy_logs.bytes_sent IS 'Total bytes sent from the client to the destination.';
COMMENT ON COLUMN proxy_logs.bytes_received IS 'Total bytes received from the destination to the client.';
COMMENT ON COLUMN proxy_logs.connection_duration_ms IS 'Total duration of the connection in milliseconds.';
COMMENT ON COLUMN proxy_logs.throughput_kbps IS 'Calculated average throughput in kilobytes per second.';
COMMENT ON COLUMN proxy_logs.status IS 'The final status of the connection.';
COMMENT ON COLUMN proxy_logs.error_message IS 'Details of any error that occurred during the connection.';
