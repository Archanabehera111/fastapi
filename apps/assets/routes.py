from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status, Query
from fastapi.responses import StreamingResponse
from apps.configs.routes import get_mappings_by_id
from database import connect_db
import pandas as pd
import psycopg2
import json
import uuid
import ipaddress
from decimal import Decimal
from datetime import datetime
from apps.assets.helpers import get_bu_id_by_format_id, get_sbu_id, get_excluded_columns, get_asset_by_id, save_filter
from apps.assets.helpers import get_all_filters, update_filter, is_password_protected, get_update_columns
from apps.assets.helpers import generate_aggregate_query, fetch_all_assets, get_insert_update_count, get_formatted_names
from apps.assets.helpers import get_filter, get_all_ips, insert_vulnerabilities, bulk_insert_uim_data, check_format
from apps.assets.helpers import fetch_vulerabilites, fetch_packages, preprocess
from logger import logger
from io import BytesIO
from typing import List, Optional
from dotenv import dotenv_values
from utils.string import snake_case
from apps.assets.schema import SearchRequest, SaveFiltersRequest, GetFiltersByUserIdRequest, UpdateFilterRequest, UpdateAssetRequest

env_config = dotenv_values(".env")

assets = APIRouter()

@assets.get("/{asset_id}/packages")
def get_asset_packages(asset_id: str, db: psycopg2.extensions.connection = Depends(connect_db)):
    packages = fetch_packages(db, asset_id)
    if db:
        db.close()
    return {
        "message": "Packages fetched successfully",
        "data": packages
    }

@assets.get("/{asset_id}")
def get_asset(asset_id: str, db: psycopg2.extensions.connection = Depends(connect_db)):
    asset = get_asset_by_id(db, asset_id)
    if db:
        db.close()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {
        "message": "Asset fetched successfully",
        "data": asset
    }

@assets.post("/upload")
async def create_assets(file: UploadFile = File(...), format_id: str = Form(...), db: psycopg2.extensions.connection = Depends(connect_db)):
    cursor_assets = db.cursor()
    bu_id = get_bu_id_by_format_id(db, format_id)
    if file.filename == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No selected file")
    
    file_content = await file.read()
    
    if len(file_content) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    # Use BytesIO to treat the bytes as a file-like object for pandas
    df = pd.read_excel(BytesIO(file_content))

    # Ensure headers are used as keys
    data_list = df.to_dict(orient='records')

    # Construct the final JSON structure
    data = {
        "assets": data_list
    }

    keys = list(df.columns)
    config_fields = get_mappings_by_id(format_id, db=db)
    excel_field_for_ip = next(item['excel_field'] for item in config_fields["mappings"] if item['asset_field'] == 'ip_address')
    try:
        # data = result #json.loads(asset_lists)
        batch_insert_values = []
        all_ip_address = []
        invalid_ip_rows = []
        invalid_ip_count = 0
        total_records = 0
        for asset in data.get('assets', []):
            total_records += 1
            columns = []
            values = []
            ip_address = []
            additional = []
            extras = []
            try:
                ipaddress.ip_address(str(asset[f"{excel_field_for_ip}"])) 
            except:
                invalid_ip_count += 1
                invalid_ip_rows.append(total_records)
                continue

            for key in keys:
                result = next((item for item in config_fields["mappings"] if item['excel_field'] == key), None)
                if result:
                    available_column = result["asset_field"]
                    if available_column == 'sbu':
                        columns.append('sbu_id')
                        values.append(get_sbu_id(db, bu_id, asset[key]))
                    elif available_column == 'additional':
                        additional.append({key: str(asset[key])})
                    else:
                        columns.append(available_column)
                        val = asset[key]
                        if type(val) == str:
                            val = val.strip()
                        values.append(val)
                        if '_unformatted' in available_column:
                            new_key = available_column.replace('_unformatted', '')
                            columns.append(new_key)
                            values.append(get_formatted_names(new_key, val, db))
                    if available_column == 'ip_address':
                        ip_address.append(asset[key])
                else:
                    extras.append({key: str(asset[key])})

            if len(additional):
                columns.append('additional')
                values.append(json.dumps(additional))

            if len(extras):
                columns.append('extras')
                values.append(json.dumps(extras))


            columns.append("id")
            column_names = '", "'.join(columns)
            placeholders = ', '.join(['%s'] * len(columns))
            values.append(str(uuid.uuid4()))
            batch_insert_values.append(values)
            all_ip_address.append(ip_address)

        insert_values = [tuple(item) for item in batch_insert_values]
        inserted_ips = [tuple(item) for item in all_ip_address]
        sql = f"""INSERT INTO assets ("{column_names}") VALUES ({placeholders}) on conflict (ip_address, host_name) do update set {get_excluded_columns()}"""
        cursor_assets.executemany(sql, insert_values)

        db.commit()

        counts = get_insert_update_count(cursor_assets, inserted_ips)
        inserted_count, updated_count = counts

        response = { 
            "message": f"Upload successful! Inserted {inserted_count} new assets and updated {updated_count} assets. Found {invalid_ip_count} invalid IPs.", 
            "no_records": total_records,
            "invalid_records": invalid_ip_count,
            "invalid_ip_rows": invalid_ip_rows,
            "inserted_count": inserted_count,
            "updated_count": updated_count
        }
        return response
    except Exception as e:
        logger.error("error while inserting", e)
        db.rollback()
        if not 'duplicate' in str(e):
            logger.error(e)
    finally:
        if db:
            db.close()

@assets.post("/search", response_model=dict)
async def read_assets(body: SearchRequest, db: psycopg2.extensions.connection = Depends(connect_db)):
    # Convert Pydantic model to dictionary
    body_dict = body.dict()

    # Call the fetch function with the deserialized body
    column_names, assets, count = fetch_all_assets(db, body_dict, 'search')
    if db:
        db.close()

    # Convert list of tuples to list of dictionaries
    converted_assets = [
        {key: (float(value) if isinstance(value, Decimal) else value) for key, value in zip(column_names, row)}
        for row in assets
    ]

    # Create the response
    response = {
        "total": count,
        "page": body.page,
        "size": body.size,
        "records": converted_assets,
    }

    return response

@assets.put("/{asset_id}")
def update_assets(
    asset_id: str, 
    body: UpdateAssetRequest,  # Use the input schema here
    db: psycopg2.extensions.connection = Depends(connect_db)
):
    cursor_assets = db.cursor()

    try:
        asset = get_asset_by_id(db, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        update_fields, update_values = get_update_columns(body.dict())

        if not update_fields:
            raise HTTPException(status_code=400, detail="No valid fields provided for update")

        if len(update_fields) != len(update_values):
            raise HTTPException(status_code=500, detail="Mismatch between fields and values")

        update_query = f"UPDATE assets SET {', '.join(update_fields)} WHERE id = '{asset_id}'"
        cursor_assets.execute(update_query, tuple(update_values))
        db.commit()
        return {
            "message": "Asset updated successfully"
        }
    except Exception as e:
        logger.error("Error while updating asset", e)
        db.rollback()
        if 'duplicate' not in str(e):
            logger.error(e)
    finally:
        if db:
            db.close()

@assets.post("/aggregate")
def get_aggregate(body: dict={}, db: psycopg2.extensions.connection = Depends(connect_db)):
    filters = body.get("filters", {})
    key = body.get("key", None)

    if not key:
        raise HTTPException(status_code=400, detail="Key is mandatory.")

    with db.cursor() as cur:
        cur.execute(generate_aggregate_query(key, filters))
        data = cur.fetchall()

    if db:
        db.close()

    return {d[0]: d[1] for d in data}

@assets.post("/download")
def download_assets(body: dict={}, db: psycopg2.extensions.connection = Depends(connect_db)):

    column_names, assets, _ = fetch_all_assets(db, body, 'download')

    if db:
        db.close()
    try:
        # Convert list of tuples to list of dictionaries
        converted_assets = [dict(zip(column_names, row)) for row in assets]

        data = preprocess(converted_assets)

        query_result = json.loads(json.dumps(data))

        # query_result = json.loads(json.dumps(converted_assets))

        df = pd.DataFrame(query_result)

        output = BytesIO()
        df.to_excel( output, index=False, engine="openpyxl" )
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = body.get("filename", None)

        if name is None:
            download_filename = f"assets_{timestamp}"
        else:
            download_filename = f"{name}_{timestamp}"
        # Print the result in JSON format
        response = StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={download_filename}.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=e)

    return response


@assets.post("/consolidate_unformatted")
async def consolidate_unformatted_fields(db: psycopg2.extensions.connection = Depends(connect_db)):
    fields_query = f"""select distinct(asset_field) from file_format_mappings where asset_field like '%_unformatted'"""
    with db.cursor() as cur:
        cur.execute(fields_query)
        fields = [f[0] for f in cur.fetchall()]

    for unformatted_field in fields:
        formatted_field = unformatted_field.split('_unformatted')[0]
        with db.cursor() as cur:
            query = f"""
                update assets a
                set {formatted_field} = fn.formatted_name 
                from formatted_names fn 
                where lower(a.{unformatted_field}) = lower(fn.name)
                and fn."type" = '{formatted_field}'
            """
            cur.execute(query)

            # Update null values
            update_null_query = f"""
                update assets a set {formatted_field} = {unformatted_field} where {formatted_field} is null;
            """
            cur.execute(update_null_query)
            
            db.commit()
    if db:
        db.close()
    
    return {
        "message": "Assets formatted successfully"
    }


@assets.post("/save_filters")
async def save_filters(body: SaveFiltersRequest, db: psycopg2.extensions.connection = Depends(connect_db)):
    user_id = body.userId
    name = body.name
    filters = body.filters
    fields = body.fields

    try:
        data = save_filter(db, name, user_id, filters, fields)
        return {
            "message": "Filters saved successfully!",
            "data": data
        }
    except:
        return {
            "message": "Something went wrong :(",
            "data": None
        }
    finally:
        if db:
            db.close()
    
@assets.post("/get_filters_by_user_id")
async def get_filters_by_user_id(body: GetFiltersByUserIdRequest, db: psycopg2.extensions.connection = Depends(connect_db)):
    user_id = body.userId
    filters = get_all_filters(db, user_id)
    
    db.close()
    
    return {
        "message": "Filters fetched successfully!",
        "data": filters
    }

@assets.post("/update_filter_by_id")
async def get_filters_by_user_id(body: UpdateFilterRequest, db: psycopg2.extensions.connection = Depends(connect_db)):
    id = body.get("id")
    filters = body.get("filters")
    fields = body.get("fields")
    name = body.get("name")
    if update_filter(db, id, name, filters, fields):
        return {
            "message": "Filters updated succesfully!"
        }
    return {
        "message": "Something went wrong :("
    }

@assets.post("/get_fitler_by_id", tags=["Assets"])
async def get_filter_by_id(body: dict={}, db: psycopg2.extensions.connection = Depends(connect_db)):
    id = body.get("id")
    filters = get_filter(db, id)
    if db:
        db.close()
    return {
        "message": "Filter fetched succesfully!",
        "data": filters
    }


@assets.post("/upload_va_reports", tags=["Assets"])
async def upload_va_reports(file: UploadFile = File(...), db: psycopg2.extensions.connection = Depends(connect_db)):
    """
        This method accepts an excel file
         * Read through sheets those have required columns like ["IP Address", "CVE"], ["IP Address/Impacted URL", "CVE ID "], ["Host", "CVE"]
         * Renames ip related and cve related columns to "IP Address" and "CVE" respectively
         * Use IP address to create a unique key
         * Parse CVE column and create a list
    """
    if file.filename == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No selected file")
    
    file_content = await file.read()
    
    if len(file_content) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    # Check if file is password protected
    if is_password_protected(file_content):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is corrupt or possibly password protected")

    # Read thru specified sheet in the excel file
    results = check_format(file_content)

    cves = pd.DataFrame(columns=['IP Address', 'CVE'])
    ips_in_db = get_all_ips(db)

    for sheet in results:
        logger.debug('Reading excel file...')
        # Use BytesIO to treat the bytes as a file-like object for pandas, also specify column to read
        df = pd.read_excel(BytesIO(file_content), sheet_name=sheet["sheet_name"], engine="openpyxl", skiprows=sheet["skip_rows"],  usecols=sheet["columns"], dtype=str)
        logger.debug('Done reading...')
        logger.debug(df.shape)
        # Renaming columns
        df.rename(columns={sheet["columns"][0]: "IP Address"}, inplace=True)
        df.rename(columns={sheet["columns"][1]: "CVE"}, inplace=True)

        df = df[['IP Address', 'CVE']]
        # Drop rows with na in cve column
        df = df.dropna(subset=['CVE'])
        # Drop rows where ip not in db
        df = df[df['IP Address'].isin(ips_in_db)]
        # Retain only ip address and cve columns
        # print size of df
        logger.debug(df.shape)
        # Group by ip address and create a list of cves
        # df = df.groupby('IP Address')['CVE'].apply(lambda x: ','.join(x)).reset_index()
        # Merge to cves dataframe, if ip already exists, append cves
        cves = pd.concat([cves, df], ignore_index=True)
    
    
    logger.debug(cves)
    cves = cves.groupby('IP Address')['CVE'].apply(lambda x: ','.join(x)).reset_index()
    # Convert dataframe to dictionary with IP as key and CVE as values
    cves_dict = cves.set_index('IP Address')['CVE'].to_dict()
    logger.debug("CVES:")
    logger.debug(len(cves_dict.keys()))
    
    inserted_count, updated_count = insert_vulnerabilities(db, cves_dict)

    unique_ip_count = len(list(cves_dict.keys()))

    unique_cves = set()

    for value in cves_dict.values():
        cve_list = value.split(',')
        unique_cves.update(cve_list)

    unique_cves_count = len(list(unique_cves))

    if db:
        db.close()

    response = { 
        "message": f"Upload successful! Inserted {inserted_count} new vulnerabilities and updated {updated_count} vulnerabilities.", 
        "no_records": inserted_count+updated_count,
        "ip_count": unique_ip_count,
        "cves_count": unique_cves_count,
        "inserted_count": inserted_count,
        "updated_count": updated_count
    }
    return response


# Update your route to pass the batch size (if necessary)
@assets.post("/upload_uim_file")
async def upload_uim_files(
    file: UploadFile = File(...),
    db: psycopg2.extensions.connection = Depends(connect_db)
):
    updated_count = 0  # Initialize a counter for updated records
    UIM_IDENTIFIER_COLUMN = snake_case(env_config["UIM_IDENTIFIER_COLUMN"])

    try:
            # Read the Excel file into a pandas DataFrame
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        data = []
        # Clean up the column names (replace newline \n with space)
        df.columns = [snake_case(col) for col in df.columns]
        ips_in_db = get_all_ips(db)
        df = df[df[UIM_IDENTIFIER_COLUMN].isin(ips_in_db)]

        # Iterate over the DataFrame and process each row
        for _, row in df.iterrows():
            ip_address = row.get(UIM_IDENTIFIER_COLUMN)

            # Ensure the UIM identifier column is a valid string and not NaN
            if pd.isna(ip_address) or not isinstance(ip_address, str):
                continue  # Skip rows where the identifier is missing or invalid

            # Convert the entire row into a dictionary for JSONB storage in UIM
            uim_data = row.to_dict()
            uim_data.pop(UIM_IDENTIFIER_COLUMN)

            data.append((json.dumps(uim_data), ip_address))

            # Increment the count for successful updates
            updated_count += 1

        # Process data in batches
        bulk_insert_uim_data(db, data)

        # Commit the transaction
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if db:
            db.close()

    return {
        "message": "Files processed and database updated successfully",
        "updated_records": updated_count  # Return the number of records updated
    }


@assets.post("/get_vulnerabilities")
def get_vulnerabilities(body: dict={}, db: psycopg2.extensions.connection = Depends(connect_db), download: Optional[bool] = Query(False)):
    column_names, assets, count = fetch_vulerabilites(db, body, 'download' if download else 'search')
    db.close()
    # Convert list of tuples to list of dictionaries
    converted_assets = [dict(zip(column_names, row)) for row in assets]

    if download:
        df = pd.DataFrame(converted_assets)
        output = BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = body.get("filename", None)

        if name is None:
            download_filename = f"vulnerabilities_{timestamp}"
        else:
            download_filename = f"{name}_{timestamp}"
        # Print the result in JSON format
        response = StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={download_filename}.xlsx"}
        )

        return response

    # Print the result in JSON format
    response = {
        "total": count,
        "page": body.get("page", 1),
        "size": body.get("size", 10),
        "records":  json.loads(json.dumps(converted_assets))
    }
    return response


@assets.post("/upload-files")
async def upload_files(file: UploadFile = File(...), db: psycopg2.extensions.connection = Depends(connect_db)):
    cursor = db.cursor()

    # Check if a file is uploaded
    if file.filename == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected for upload")
    
    # Read the file content
    file_content = await file.read()
    
    if len(file_content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    
    # Load the Excel file into a DataFrame
    try:
        df = pd.read_excel(BytesIO(file_content))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error reading Excel file: {str(e)}")
    
    # Expected columns in the table
    required_columns = {"ipaddress", "country", "name"}
    excel_columns = set(df.columns)

    # Check if required columns are in the uploaded file
    if not required_columns.issubset(excel_columns):
        missing_columns = required_columns - excel_columns
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data is invalid"
        )

    try:
        # Track the number of rows processed
        processed_count = 0

        for _, row in df.iterrows():
            ipaddress = row.get("ipaddress")
            country = row.get("country")
            name = row.get("name")
            
            # Use ON CONFLICT to handle insert or update in one query
            cursor.execute(
                """
                INSERT INTO demo_table (ipaddress, country, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (ipaddress)
                DO UPDATE SET
                    country = EXCLUDED.country,
                    name = EXCLUDED.name;
                """,
                (ipaddress, country, name)
            )
            processed_count += 1

        # Commit the transaction
        db.commit()

        return {
            "message": "File processed successfully!",
            "processed_count": processed_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing the file: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing the file")
    finally:
        if db:
            db.close()


