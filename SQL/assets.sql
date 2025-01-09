-- assets.sql

-- Create table if not exists
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY,
    sbu_id UUID,
    application VARCHAR,
    model_name VARCHAR,
    type VARCHAR,
    sub_type VARCHAR,
    category VARCHAR,
    tag VARCHAR,
    manufacturer_unformatted VARCHAR,
    manufacturer VARCHAR,
    manufacturer_part_no VARCHAR,
    manufacturer_serial_no VARCHAR,
    status VARCHAR,
    sub_status VARCHAR,
    ownership VARCHAR,
    location_id VARCHAR,
    zone VARCHAR,
    circle VARCHAR,
    city VARCHAR,
    location_address VARCHAR,
    location_name VARCHAR,
    user_name VARCHAR,
    user_email VARCHAR,
    user_department VARCHAR,
    user_employee_id VARCHAR,
    ip_address VARCHAR,
    host_name VARCHAR,
    os_name_unformatted VARCHAR,
    os_name VARCHAR,
    os_version VARCHAR,
    criticality VARCHAR,
    service_provider VARCHAR,
    warranty_expiry DATE,
    end_of_life DATE,
    end_of_support_date DATE,
    end_of_support_status VARCHAR,
    comments VARCHAR,
    notes VARCHAR,
    extras JSON,
    additional JSON,
    risk_score FLOAT,
    FOREIGN KEY (sbu_id) REFERENCES sbu(id) -- Foreign key constraint
);

-- Example: Adding an index on id
CREATE INDEX idx_assets ON assets (location_id, user_employee_id, sbu_id);

-- Create unique index - this is our identifier for now
CREATE UNIQUE INDEX idx_assets_ip_address_host_name on assets (ip_address, host_name);

-- Creating one more column in the table
ALTER TABLE assets ADD COLUMN uim JSONB;