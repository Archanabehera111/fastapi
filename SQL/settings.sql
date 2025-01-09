-- settings.sql

-- Create the table
CREATE TABLE IF NOT EXISTS saved_fields (
    id UUID PRIMARY KEY,
    user_id VARCHAR,
    fields JSON,
    table_name VARCHAR,
    UNIQUE (user_id, table_name)
);
