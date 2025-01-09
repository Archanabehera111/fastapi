-- asset_file_formats.sql

-- Create the table
CREATE TABLE IF NOT EXISTS asset_file_formats (
    id UUID PRIMARY KEY,
    name varchar,
    user_id varchar,
    deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Example: Adding an index on id and user_id
CREATE INDEX idx_asset_file_formats ON asset_file_formats (user_id);