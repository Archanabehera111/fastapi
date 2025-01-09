-- sbu.sql

-- Create the table
CREATE TABLE IF NOT EXISTS sbu (
    id UUID PRIMARY KEY NOT NULL,
    name varchar,
    bu_id UUID NOT NULL,
    FOREIGN KEY (bu_id) REFERENCES bu(id) -- Foreign key constraint
);

-- Example: Adding an index on id and user_id
CREATE INDEX idx_sbu ON sbu (bu_id);


