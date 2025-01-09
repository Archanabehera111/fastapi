from database import connect_db
from logger import logger
from functools import lru_cache

@lru_cache(maxsize=128)
def generate_fields(table_name, short_name):
    # Generate fields for the given table
    fields_string = ""
    fields = get_fields(table_name)
    for field, type in fields.items():
        if type == 'jsonb':
            for json_field in extract_json_fields(table_name, field):
                fields_string += f"{short_name}.{field}->'{json_field}' as {field}_{json_field}, "
        elif type == 'date':
            # Cast date to string
            fields_string += f"to_char({short_name}.{field}, 'YYYY-MM-DD') as {field}, "
        else:
            fields_string += f"{short_name}.{field}, "
    # Remove trailing comma
    fields_string = fields_string[:-2]
    return fields_string

@lru_cache(maxsize=128)
def get_fields(table_name, type=None):
    # Get fields for the given table
    fields = []
    conn = connect_db()
    with conn.cursor() as cur:
        query = f"""SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}' {" and data_type = '" + type + "'"  if type else ''} order by 2, 1"""
        logger.debug(query)
        cur.execute(query)
        fields = {field[0]: field[1] for field in cur.fetchall()}
    conn.close()
    return fields

@lru_cache(maxsize=128)
def extract_json_fields(table_name, field):
    # Extract json fields from the given field
    fields = []
    conn = connect_db()
    with conn.cursor() as cur:
        query = f"select distinct jsonb_object_keys({field}) from {table_name}"
        logger.debug(query)
        cur.execute(query)
        fields = [field[0] for field in cur.fetchall()]
    conn.close()
    return fields
