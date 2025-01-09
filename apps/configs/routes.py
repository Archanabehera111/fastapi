# routes/configs.py
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
import psycopg2
import json
from database import connect_db
from apps.configs.helpers import res_to_config_format, get_all_bu, res_to_bu_format, get_all_configs
import uuid

conn = None
mock_data = None
response = None


configs = APIRouter()

@configs.get("/bu")
def get_all_bu_sbu(db: psycopg2.extensions.connection = Depends(connect_db)):
    try:
        
        results = get_all_bu(db)

        all_bus = res_to_bu_format(results)

        response = {
            "total": len(all_bus),
            "all_bus": all_bus
        }

        return {"result": response}
        
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        # Close cursor and connection
        db.close()

# @configs.post("/search")
# def get_all_asset_configs(body: dict={}, db: psycopg2.extensions.connection = Depends(connect_db)):
#     try:        
#         # Fetch all results
#         results = get_all_configs(body, db)

#         configs = res_to_config_format(results)

#         response = {
#             "total": len(configs),
#             "configs": configs
#         }

#         return {"result": response}
        
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")
#     finally:
#         # Close cursor and connection
#         db.close()


@configs.post("/search")
def get_all_asset_configs(body: dict = {}, db: psycopg2.extensions.connection = Depends(connect_db)):
    try:
        print(f"Received request body: {body}")
        id = body.get("id")

        if not id:
            raise HTTPException(status_code=400, detail="ID is required in the request body.")

        # Fetch results based on ID
        results = get_all_configs(body, db)  # Ensure `id` is used in the query inside `get_all_configs`

        if not results:
            raise HTTPException(status_code=404, detail=f"No config found with ID: {id}")

        configs = res_to_config_format(results)

        response = {
            "total": len(configs),
            "configs": configs
        }

        return {"result": response}

    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        db.close()


@configs.post("/")
def create_new_mapping(body:dict={}, db: psycopg2.extensions.connection = Depends(connect_db)):
    mappings = body.get("mappings", [])
    name = body.get("name", "")
    user_id = body.get("userId", "")
    cursor = db.cursor()
    try:
        cursor.execute(f'''
            insert into asset_file_formats values (
                '{uuid.uuid4()}',
                '{name}',
                '{user_id}',
                {False},
                '{datetime.now()}',
                '{datetime.now()}'
            )
            RETURNING id;
        ''')

        inserted_id = cursor.fetchone()[0]
        
        for mapping in mappings:
            cursor.execute(f'''
                insert into file_format_mappings values (
                    '{uuid.uuid4()}',
                    '{inserted_id}',
                    '{mapping['excelField']}',
                    '{mapping["assetField"]}'
                );
            ''')


        db.commit()
        return { "message" : "Mapping created successfully", "id" : inserted_id}
    except Exception as e:
        print("error while inserting", e)
        db.rollback()
        if not 'duplicate' in str(e):
            print(e)
    finally:
        db.close()

@configs.get("/{config_id}")
def get_mappings_by_id(config_id:str, db: psycopg2.extensions.connection = Depends(connect_db)):
    cursor = db.cursor()
    try:
        # Define the SQL query
        query = '''
            SELECT
                aff.id AS format_id,
                aff.name,
                aff.user_id,
                aff.deleted,
                aff.created_at,
                aff.updated_at,
                ffm.id AS mapping_id,
                ffm.excel_field as excel_field,
                ffm.asset_field as asset_field
            FROM
                asset_file_formats aff
            INNER JOIN
                file_format_mappings ffm
            ON
                aff.id = ffm.format_id
            WHERE deleted = false
            AND aff.id = %s
        '''

        # Execute the query with parameter
        cursor.execute(query, (config_id,))
        
        # Fetch all results
        results = cursor.fetchall()

        if not results:
            return HTTPException(status_code=404, detail="Record not found or already deleted")
        
        response = res_to_config_format(results)
        return response[0]

    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        # Close cursor and connection
        cursor.close()
        db.close()

@configs.put("/{config_id}")
def update_mapping(config_id: str, body: dict = {}, db: psycopg2.extensions.connection = Depends(connect_db)):
    mappings = body.get("mappings", [])
    name = body.get("name", "")
    userId = body.get("userId", "")
    
    # Check if 'mappings' key is present and is a list
    if not isinstance(mappings, list):
        raise HTTPException(status_code=400, detail="Invalid data, 'mappings' should be a list")

    # Extract 'excelField' and 'assetField' values
    data = {
        "excel_fields": {mapping.get("excelField") for mapping in mappings if "excelField" in mapping},
        "asset_fields": {mapping.get("assetField") for mapping in mappings if "assetField" in mapping}  # Set
    }
    data["excel_fields"] = list(data["excel_fields"])
    data["asset_fields"] = list(data["asset_fields"])

    print("excel_fields", data["excel_fields"])
    print("asset_fields", data["asset_fields"])
    print("name", name)
    
    cursor = db.cursor()
    try:
        query = '''
            SELECT
                aff.id AS format_id,
                aff.name,
                aff.user_id,
                aff.deleted,
                aff.created_at,
                aff.updated_at,
                ffm.id AS mapping_id,
                ffm.excel_field as excel_field,
                ffm.asset_field as asset_field
            FROM
                asset_file_formats aff
            INNER JOIN
                file_format_mappings ffm
            ON
                aff.id = ffm.format_id
            WHERE aff.id = %s
        '''

        print("before start get mapping")

        # Execute the query with parameter
        cursor.execute(query, (config_id,))
        
        record = cursor.fetchall()
        # record = get_mappings_by_id(config_id, db)
        print("after start get mapping")
        print("record", record)

        # print("record[Result]", record["Result"])
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        print("sucess")
        # Update the record
        cursor.execute(f'''
            UPDATE asset_file_formats
            SET name = %s, user_id = %s
            WHERE id = %s
        ''', (name, userId, config_id))

        print("Updated record id", config_id)
        print("json value", json.dumps(data["excel_fields"]))

        cursor.execute(f'''
            UPDATE file_format_mappings
            SET format_id = %s, excel_field = %s, asset_field = %s
        ''', (config_id, json.dumps(data["excel_fields"]), json.dumps(data["asset_fields"])))

        db.commit()
        return { "message" : "Mapping updated successfully", "userID" : userId}
    except Exception as e:
        print("error while updating", e)
        db.rollback()
        if 'duplicate' not in str(e):
            print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        db.close()
    
@configs.delete("/{config_id}")
def delete_mapping(config_id: str, db: psycopg2.extensions.connection = Depends(connect_db)):
    cursor = db.cursor()
    try:
        # Check if record exists
        query = '''
            SELECT 1
            FROM asset_file_formats
            WHERE id = %s AND deleted = FALSE
        '''
        cursor.execute(query, (config_id,))
        record_exists = cursor.fetchone()
        
        if not record_exists:
            raise HTTPException(status_code=404, detail="Record not found or already deleted")

        # Soft delete from asset_file_formats
        cursor.execute('''
            UPDATE asset_file_formats
            SET deleted = TRUE
            WHERE id = %s
        ''', (config_id,))

        db.commit()
        return { "message" : "Config deleted successfully"}

    except psycopg2.Error as e:
        db.rollback()
        print("Error while soft deleting:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        cursor.close()
        db.close()
