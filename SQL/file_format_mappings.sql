-- file_format_mappings.sql

-- Create the table
CREATE TABLE IF NOT EXISTS file_format_mappings (
    id UUID PRIMARY KEY,
    format_id UUID NOT NULL,
    excel_field VARCHAR,
    asset_field VARCHAR,
    FOREIGN KEY (format_id) REFERENCES asset_file_formats(id)
);

-- Create an index on format_id
CREATE INDEX idx_file_format_mappings ON file_format_mappings (format_id);

-- End of file
