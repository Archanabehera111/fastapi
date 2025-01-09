-- formatted_names.sql

-- Create the table
CREATE TABLE IF NOT EXISTS formatted_names (
    name varchar not null,
    formatted_name varchar not null,
    "type" varchar not null
);


-- Make name, and type field as unique key
create unique index idx_formatted_names_name_type on formatted_names (name, type);
