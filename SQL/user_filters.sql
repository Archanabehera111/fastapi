-- assets_user_filters.sql

-- Enable pgcrypto if not already done. This is to auto generate UUID 
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create the table
CREATE TABLE IF NOT EXISTS saved_filters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR,
    user_id VARCHAR not null,
    filters JSONB,
    fields JSONB,
    table_name VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
