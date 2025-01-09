from functools import lru_cache
from uuid import uuid4
from datetime import datetime, date
import json
import psycopg2
from psycopg2 import sql
import psycopg2.extras
from logger import logger
from io import BytesIO
from decimal import Decimal
import pandas as pd
from utils.database import generate_fields, get_fields
from dotenv import dotenv_values



# Load the .env file
env_config = dotenv_values(".env")
# Access the VA_COLUMNS variable
va_columns_str = env_config['VA_COLUMNS']
VA_COLUMNS = json.loads(va_columns_str)
tables = ["assets", "bu", "sbu"]

upsert_columns = [
    "model_name",
    "type",
    "sub_type",
    "category",
    "tag",
    "manufacturer",
    "manufacturer_part_no",
    "manufacturer_serial_no",
    "status",
    "sub_status",
    "ownership",
    "location_id",
    "zone",
    "circle",
    "city",
    "location_address",
    "location_name",
    "user_name",
    "user_email",
    "user_department",
    "user_employee_id",
    "os_name",
    "os_version",
    "criticality",
    "service_provider",
    "warranty_expiry",
    "end_of_life",
    "end_of_support_date",
    "end_of_support_status",
    "comments",
    "notes",
    "extras",
    "additional"
]

filter_select_columns = ["id", "name", "filters", "fields"]

@lru_cache
def get_bu_id_by_format_id(db, format_id):
    id = None
    try:
        sql = f"select bu.id from bu, asset_file_formats aff where bu.name = aff.name and aff.id = '{format_id}'"
        with db.cursor() as cur:
            cur.execute(sql)
            id = cur.fetchone()[0]
    except Exception as e:
        print(str(e))
    finally:
        return id

@lru_cache
def get_sbu_id(db, bu_id, name):
    sbu_id = None
    try:
        with db.cursor() as cur:
            cur.execute(f"select id from sbu where name = '{name}' limit 1")
            sbu_id = cur.fetchone()[0]
    except:
        with db.cursor() as cur:
            print(f'SBU not found, creating new record for {name}.')
            cur.execute(f"insert into sbu (id, bu_id, name) values ('{uuid4()}', '{bu_id}', '{name}') returning id")
            sbu_id = cur.fetchone()[0]
        db.commit()
    finally:
        return sbu_id

@lru_cache
def get_excluded_columns():
    return f"({', '.join(upsert_columns)}) = ({', '.join([f'excluded.{c}' for c in upsert_columns])})"

@lru_cache
def get_asset_fields():
    return f" bu.name as bu_name, sbu.name as sbu_name, {generate_fields('assets', 'a')} "

@lru_cache(maxsize=128)
def get_asset_by_id(db, asset_id):
    asset = None
    try:
        column_names, assets, _ = fetch_all_assets(db,  {"filters": {"a.id": [asset_id]}}, 'search')
        asset = [dict(zip(column_names, row)) for row in assets][0]
    except Exception as e:
        logger.error(str(e))
    finally:
        return asset

def get_update_columns(body):
    update_fields = []
    update_values = []

    for key, value in body.items():
        if key in upsert_columns:
            if isinstance(value, (dict, list)) and value is not None:
                update_fields.append(f"{key} = %s")
                update_values.append(json.dumps(value))
            elif value is not None:
                update_fields.append(f"{key} = %s")
                update_values.append(value)

    return update_fields, update_values

def generate_aggregate_where_clause(filters):
    where = ""
    if filters:
        for (key, val) in filters.items():
            fil_col = 'bu.id' if key == "bu_id" else 'sbu.id' if key == "sbu_id" else f'a.{key}'
            if type(val) == list:
                where += f""" and {fil_col} in ('{"','".join(val)}') """
            else:
                where += f""" and {fil_col} = '{val}' """
    return where

def process_filters(filters):
    # Handle jsonb fields for search
    new_filters = {}
    jsonb_fields = get_fields('assets', 'jsonb')
    for key, value in filters.items():
        splits = key.split('_', 1)
        if splits[0] in jsonb_fields:
            new_filters[f"LOWER({splits[0]}->>'{splits[1]}')"] = value
        else:
            new_filters[key] = value
    return new_filters

def generate_aggregate_query(key, filters):
    filters = process_filters(filters)
    agg_col = 'bu.id' if key == "business_unit" else 'sbu.id' if key == "sub_business_unit" else f'a.{key}'
    json_cols = get_fields('assets', 'jsonb')
    splits = key.split('_', 1)
    if splits[0] in json_cols:
        agg_col = f"a.{splits[0]}->>'{splits[1]}'"

    query = f"""
        select {agg_col}, count(a.id) from assets a, bu, sbu
        where sbu.id = a.sbu_id and bu.id = sbu.bu_id
        {generate_aggregate_where_clause(filters)}
        group by {agg_col}
    """
    logger.debug(f"Aggregate Query:\n {query}")
    return query

def get_string_columns(tables, db):
    table_columns = {}
    for table in tables:
        with db.cursor() as cur:
            cur.execute(sql.SQL("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public';  -- Ensure the right schema
            """), [table])

            columns = cur.fetchall()
            table_columns[table] = columns

    string_types = ['character varying', 'text', 'char']

    string_columns = []
    for table, columns in table_columns.items():
        for column_name, data_type in columns:
            if data_type in string_types:
                string_columns.append(column_name)

    return string_columns

def fetch_all_assets(db, body, action):
    page = body.get("page", 1)
    size = body.get("size", 10)
    filters = process_filters(body.get("filters", body.get("filter", {})))
    logger.debug(f"Filters: {filters}")
    download_columns = body.get("download_columns", [])
    order_by = body.get("sort", {})

    try:
        query = f"SELECT {get_asset_fields()} FROM assets a, bu, sbu WHERE sbu.id = a.sbu_id and bu.id = sbu.bu_id "
        params = []
        f_query = ""
        string_columns = get_string_columns(tables, db)
        for key, values in filters.items():
            key = "bu.id" if key == "bu_id" else "sbu.id" if key == "sbu_id" else "a.id" if key == "id" else key
            values = [
                value.lower() if isinstance(value, str) else value
                for sublist in values
                for value in (sublist if isinstance(sublist, list) else [sublist])
            ]
            if key in string_columns:
                f_query += f""" AND LOWER({key}) in ({", ".join(["%s" for _ in range(len(values))])})"""
            else:
                f_query += f""" AND {key} in ({", ".join(["%s" for _ in range(len(values))])})"""
            params.extend(values)
        if action == 'download' and len(download_columns):
            download_columns_str = ""
            json_fields = get_fields('assets', 'jsonb')
            for column in download_columns:
                if column in ['bu_name', 'sbu_name']:
                    dot = '.'.join(column.split('_'))
                    download_columns_str += f"{dot} as {column}, "
                else:
                    splits = column.split('_', 1)
                    if splits[0] in json_fields.keys():
                        download_columns_str += f"a.{splits[0]}->>'{splits[1]}' as {column}, "
                    else:
                        download_columns_str += f"a.{column} as {column}, "
            download_columns_str = download_columns_str[:-2]
            query = f"""SELECT {download_columns_str} FROM assets a, bu, sbu WHERE sbu.id = a.sbu_id and bu.id = sbu.bu_id """
        logger.debug(f"Query: {query}")

        count_query = """ select count(a.id) FROM assets a, bu, sbu WHERE sbu.id = a.sbu_id and bu.id = sbu.bu_id """
        count_query += f_query
        query += f_query
        
        with db.cursor() as cur:
            cur.execute(count_query, params)
            count = cur.fetchone()[0]

        # Handle sorting
        if order_by:
            sort_clauses = [f"{field} {direction}" for field, direction in order_by.items()]
            sort_clause = ", ".join(sort_clauses)
            query += f" ORDER BY {sort_clause}"
        else:
            query += " ORDER BY city ASC"

        # Add pagination
        if action != 'download':
            if size:
                query += " LIMIT %s OFFSET %s"
                params.extend([size, (page - 1) * size])

        logger.debug(f"Query/Params: {query}\n{params}")
        with db.cursor() as cur:
            cur.execute(query, params)
            assets = cur.fetchall()
            column_names = [desc[0] for desc in cur.description]

        return column_names, assets, count
    except Exception as e:
        logger.error(str(e))

def get_insert_update_count(cursor_assets, insert_values):
    try:
        count_query = """
            SELECT
                COUNT(*) FILTER (WHERE action = 'inserted') AS inserted_count,
                COUNT(*) FILTER (WHERE action = 'updated') AS updated_count
            FROM (
                SELECT
                    ip_address,
                    host_name,
                    CASE
                        WHEN xmax::text = '0' THEN 'inserted'
                        ELSE 'updated'
                    END AS action
                FROM assets
                WHERE ip_address IN %s
            ) AS subquery
            """
        cursor_assets.execute(count_query, (tuple(row[0] for row in insert_values),))
        counts = cursor_assets.fetchone()
        return counts
    except Exception as e:
        print(str(e))

def get_insert_update_va_count(cursor_va, insert_values):
    try:
        count_query = """
            SELECT
                COUNT(*) FILTER (WHERE action = 'inserted') AS inserted_count,
                COUNT(*) FILTER (WHERE action = 'updated') AS updated_count
            FROM (
                SELECT
                    ip_address,
                    cve_id,
                    CASE
                        WHEN xmax::text = '0' THEN 'inserted'
                        ELSE 'updated'
                    END AS action
                FROM vulnerabilities
                WHERE ip_address IN %s
            ) AS subquery
            """
        
        cursor_va.execute(count_query, (tuple(row[0] for row in insert_values),))
        counts = cursor_va.fetchone()
        return counts
    except Exception as e:
        print(str(e))

@lru_cache
def get_formatted_names(type, name, db):
    try:
        with db.cursor() as cur:
            query = 'select formatted_name from formatted_names where lower(name) = %s and type = %s limit 1'
            cur.execute(query, [name.lower(), type.lower()])
            val = cur.fetchone()[0]
            return val or name
    except Exception as e:
        print(str(e))
        return name

def save_filter(db, name, user_id, filters, fields):
    try:
        query = """insert into saved_filters (name, user_id, filters, fields, table_name, created_at, updated_at) values (%s, %s, %s, %s, %s, %s, %s) returning id, name, user_id, filters, fields, table_name"""
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, [name, user_id, json.dumps(filters), json.dumps(fields), 'asset_inventory', datetime.now(), datetime.now()])
            res = cur.fetchone()
        db.commit()
        return dict(res)
    except Exception as e:
        print(e)
        return False

def get_all_filters(db, user_id):
    query = f"""select {", ".join(filter_select_columns)} from saved_filters where user_id = %s"""
    res = []
    with db.cursor() as cur:
        cur.execute(query, [user_id])
        for r in cur.fetchall():
            res.append({c: r[i] for i, c in enumerate(filter_select_columns)})
    return res

def update_filter(db, id, name, filters, fields):
    try:
        query = "update saved_filters set name = %s, filters = %s, fields = %s, updated_at = %s where id = %s"
        with db.cursor() as cur:
            cur.execute(query, [name, json.dumps(filters), json.dumps(fields), datetime.now(), id])
        db.commit()
        return True
    except Exception as e:
        print(e)
        return False
    finally:
        db.close()

def get_filter(db, id):
    query = f"""select {", ".join(filter_select_columns)} from saved_filters where id = %s limit 1"""
    with db.cursor() as cur:
        cur.execute(query, [id])
        re = cur.fetchone()
        return {c: re[i] for i, c in enumerate(filter_select_columns)}

def get_all_ips(db):
    query = "select distinct(ip_address) from assets"
    with db.cursor() as cur:
        cur.execute(query)
        return [r[0] for r in cur.fetchall()] 

def is_password_protected(file_content):
    # Read excel fails if file is password protected
    try:
        df = pd.read_excel(BytesIO(file_content))
        return False
    except:
        return True

def bulk_insert_vulnerabilities(db, data, inserted_va_ips):
    logger.debug(f"Inserting {len(data)} vulnerabilities.")
    inserted_count = 0
    updated_count = 0
    try:
        with db.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO vulnerabilities (ip_address, cve_id)
                VALUES %s
                ON CONFLICT (ip_address, cve_id) DO UPDATE SET updated_at = now()
            """, data)
            counts = get_insert_update_va_count(cur, inserted_va_ips)
            inserted_count, updated_count = counts

        db.commit()
        return inserted_count, updated_count
    except Exception as e:
        logger.error(str(e))
        return False

def insert_vulnerabilities(db, cves_dict):
    counter = 0
    data = []
    inserted_va_ips = [(ip,) for ip in cves_dict.keys()]
    for ip, cves in cves_dict.items():
        cve_list = set(cves.split(','))
        for cve in cve_list:
            data.append((ip, cve))
            counter += 1
        if counter > 5000:
            inserted_count, updated_count = bulk_insert_vulnerabilities(db, data, inserted_va_ips)
            data.clear()
            counter = 0
    if data:
        inserted_count, updated_count = bulk_insert_vulnerabilities(db, data, inserted_va_ips)
    return inserted_count, updated_count


def bulk_insert_uim_data(db, data, batch_size=5000):
    with db.cursor() as cursor:
        # Split the data into batches
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            cursor.executemany("""
                UPDATE assets
                SET uim = %s
                WHERE ip_address = %s
            """, batch)


def detect_headers(file_content, sheet):
    df_preview = pd.read_excel(file_content, sheet_name=sheet, header=None, nrows=20)
    for i, row in df_preview.iterrows():
        # Assume headers are rows where all columns have string data
        if row.notna().all():
            return i
        

def check_format(file_content):
    try:
        # Load the Excel file
        xl =  pd.ExcelFile(BytesIO(file_content), engine='openpyxl')
        output = []

        # Iterate through all the sheets in the Excel file
        for sheet_name in xl.sheet_names:
            try:
                detect_row = detect_headers(file_content, sheet_name)
                # Read the sheet into a DataFrame
                df = xl.parse(sheet_name, skiprows=detect_row, nrows=20)
                cols = set(df.columns.to_list())
                for i in VA_COLUMNS:
                    if set(i).issubset(cols):
                        output.append({
                            "sheet_name": sheet_name,
                            "columns": i,
                            "skip_rows": detect_row
                        })

                # Remove early return to process all sheets
            except Exception as e:
                print(f"Error processing sheet {sheet_name}: {e}")

        return output  # Return results after all sheets are processed

    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except ValueError as e:
        print(f"ValueError: {e}")
    except Exception as e:
        print(f"Error loading file: {e}")


def generate_sort_clause(order_by, default):
    sort_clauses = [f"{field} {direction}" for field, direction in order_by.items()]
    sort_clause = ", ".join(sort_clauses)
    return sort_clause or default


def fetch_vulerabilites(db, data, mode='search'):
    # Get assets by filters, and get all CVEs for those assets from vulerabilities table
    filters = process_filters(data.get("filters", data.get("filter", {})))
    if "ip_address" in filters:
        filters["a.ip_address"] = filters.pop("ip_address")
    order_by = data.get("sort", {})
    page = data.get("page", 1)
    size = data.get("size", 10)
    count = 0
    logger.debug(f"Filters: {filters}")
    params = []
    default_columns = ["ip_address", "host_name", "application", "manufacturer", "model_name", "category", "type", "manufacturer_serial_no", "os_name"]
    columns = default_columns
    if mode == 'download' and "download_columns" in data:
        columns = data.get("download_columns", default_columns)
    if "ip_address" not in columns:
        columns.insert(0, "ip_address")
    columns = [f"a.{col}" for col in columns]

    f_query = ""

    for key, values in filters.items():
        key = "bu.id" if key == "bu_id" else "sbu.id" if key == "sbu_id" else key
        f_query += f""" AND {key} in ({", ".join(["%s" for _ in range(len(values))])})"""
        params.extend(values)

    logger.debug(f"FQuery: {f_query}")

    query = f"""
        select {", ".join(columns)}, STRING_AGG(v.cve_id, ',') AS cves from assets a, vulnerabilities v, bu, sbu
        where inet(a.ip_address) = inet(v.ip_address) 
        and a.sbu_id = sbu.id and sbu.bu_id = bu.id
        {f_query}
        group by {", ".join(columns)}
        order by {generate_sort_clause(order_by, "a.ip_address ASC")} 
    """

    if mode != 'download':
        query += f""" LIMIT {size} OFFSET {(page - 1) * size}"""


    logger.debug(f"Query: {query}")
    with db.cursor() as cur:
        cur.execute(query, params)
        assets = cur.fetchall()
        column_names = [desc[0] for desc in cur.description]

    if mode != 'download':
        count_query = f"""
            select count(distinct(ip_address)) from vulnerabilities v
            where ip_address in (select ip_address::inet from assets a, bu, sbu
            where a.sbu_id = sbu.id and sbu.bu_id = bu.id {f_query})
        """

        with db.cursor() as cur:
            cur.execute(count_query, params)
            count = cur.fetchone()[0]
    
    return column_names, assets, count


def filter_unique_short_names(package_info_list):
    """
        Skipping OS for now.
        Revisit this later.
    """
    unique_packages = []
    seen_short_names = set()

    for package in package_info_list:
        if package['type'] == 'o':
            continue
        short_name = package['short_name']
        if short_name not in seen_short_names:
            unique_packages.append(package)
            seen_short_names.add(short_name)

    return unique_packages


@lru_cache
def parse_cpe_uri(cpe_uri):
    try:
        parts = cpe_uri.split(':')
        if len(parts) >= 6 and parts[0] == 'cpe' and parts[1].startswith('2.'):
            return {
                'short_name': f'{parts[3]} {parts[4]}',
                'type': parts[2],
                'vendor': parts[3],
                'product': parts[4],
                'version': parts[5]
            }
        else:
            return None
    except:
            return None


@lru_cache
def fetch_packages(db, asset_id):
    cpe_uris = get_cpe_uris(db, asset_id)
    packages_info = [parse_cpe_uri(cpe_uri) for cpe_uri in cpe_uris]
    packages_info = filter_unique_short_names(packages_info)
    return packages_info


def get_cpe_uris(db, asset_id):
    query = f"""
        select cm.cpe_uri from cpe_matches cm, vulnerabilities v, assets a
        where cm.cve_id = v.cve_id and v.ip_address = a.ip_address::inet and a.id = %s
    """
    with db.cursor() as cur:
        cur.execute(query, [asset_id])
        cpe_uris = [r[0] for r in cur.fetchall()]
    return cpe_uris

def preprocess(data):
    if isinstance(data, dict):
        return {key: preprocess(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [preprocess(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, date):
        return data.isoformat()
    return data