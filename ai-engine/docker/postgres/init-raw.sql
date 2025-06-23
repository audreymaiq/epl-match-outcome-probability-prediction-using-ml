-- Tạo schema raw
CREATE SCHEMA IF NOT EXISTS raw;

-- Tạo bảng lưu trữ dữ liệu thô
CREATE TABLE raw.api_responses (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(100) NOT NULL,
    params JSONB,
    response JSONB NOT NULL,
    season INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed BOOLEAN NOT NULL DEFAULT FALSE
);

-- Indexes cho hiệu suất truy vấn
CREATE INDEX idx_raw_endpoint ON raw.api_responses(endpoint);
CREATE INDEX idx_raw_season ON raw.api_responses(season);
CREATE INDEX idx_raw_processed ON raw.api_responses(processed);
COMMENT ON TABLE raw.api_responses IS 'Bảng lưu trữ dữ liệu thô từ API Football';