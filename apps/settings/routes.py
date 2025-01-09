from fastapi import APIRouter, HTTPException, Depends
import uuid
import psycopg2
from database import connect_db
import json
from dotenv import dotenv_values
from apps.settings.schema import SaveFields, SaveFieldsOutput, SaveFieldsOutputData
from apps.settings.schema import GetFields, GetFieldsOutput, GetFieldsOutputData
from apps.settings.schema import SaveFiltersInputSchema, SaveFiltersOutputSchema, UpdateFiltersInputSchema
from apps.settings.schema import GetFiltersInputSchema, GetFiltersOutputSchema
from apps.settings.schema import DeleteFilterInputSchema, DeleteFilterOutputSchema
from logger import logger

env_config = dotenv_values(".env")

table_name_for_settings = "saved_fields"

settings = APIRouter()


@settings.post('/save_fields', response_model=SaveFieldsOutput)
async def save_fields(body: SaveFields, db: psycopg2.extensions.connection = Depends(connect_db)):
    query = f"""
    INSERT INTO {table_name_for_settings} (id, user_id, fields, table_name)
    VALUES (%s, %s, %s::jsonb, %s)
    ON CONFLICT (user_id, table_name) DO UPDATE
    SET fields = EXCLUDED.fields
    RETURNING id, user_id, fields, table_name
    """

    values = (
        str(uuid.uuid4()),  # Generate a new UUID for the primary key
        body.user_id,
        json.dumps(body.fields),  # Convert Python list to JSON before insertion
        body.table_name
    )

    try:
        with db.cursor() as cursor:
            cursor.execute(query, values)
            saved_record = cursor.fetchone()
            db.commit()

            response = SaveFieldsOutput(
                message="Fields saved successfully",
                data=SaveFieldsOutputData(
                    id=saved_record[0],
                    userId=saved_record[1],
                    fields=saved_record[2],
                    tableName=saved_record[3]
                )
            )
 
            return response
    except Exception as e:
        db.rollback()
        print(f"Error while saving fields: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save fields") from e
    finally:
        db.close()


@settings.post('/get_fields', response_model=GetFieldsOutput)
async def get_fields(body: GetFields, db: psycopg2.extensions.connection = Depends(connect_db)):
    query = f"""
    SELECT id, user_id, fields, table_name 
    FROM {table_name_for_settings}
    WHERE user_id = %s AND table_name = %s
    """

    try:
        with db.cursor() as cursor:
            cursor.execute(query, (body.user_id, body.table_name))
            result = cursor.fetchone()

            if not result:
                message = "No fields found for the given user_id and table_name"
                data = None
            else:
                message = "Fields retrieved successfully"
                data = GetFieldsOutputData(
                    id=result[0],
                    userId=result[1],
                    fields=result[2],
                    tableName=result[3]
                )
            response = GetFieldsOutput(
                message=message,
                data=data
            )
            return response
    except Exception as e:
        print(f"Error while retrieving fields: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve fields") from e
    finally:
        db.close()


@settings.post('/save_filters', response_model=SaveFiltersOutputSchema, tags=['Filters'])
def save_filters(body: SaveFiltersInputSchema, db: psycopg2.extensions.connection = Depends(connect_db)):
    query = f"""
        INSERT INTO saved_filters (user_id, filters, table_name, fields, name)
        VALUES (%s, %s::jsonb, %s, %s::jsonb, %s)
        RETURNING id, user_id, filters, table_name, fields, name
    """

    values = (
        body.user_id,
        json.dumps(body.filters),  # Convert Python dict to JSON before insertion
        body.table_name,
        json.dumps(body.fields),  # Convert Python list to JSON before insertion
        body.name
    )

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, values)
            db_record = cursor.fetchone()
            db.commit()
            return {
                "message": "Filters saved successfully",
                "data": dict(db_record)
            }
    except Exception as e:
        db.rollback()
        print(f"Error while saving filters: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save filters") from e
    finally:
        db.close()

        

    
@settings.post('/get_filters', response_model=GetFiltersOutputSchema, tags=['Filters'])
def get_filters(body: GetFiltersInputSchema, db: psycopg2.extensions.connection = Depends(connect_db)):
    query = f"""
        SELECT id, user_id, filters, table_name, fields, name
        FROM saved_filters
        WHERE user_id = %s AND table_name = %s
    """

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, (body.user_id, body.table_name))
            db_records = cursor.fetchall()
            return {
                "message": "Filters retrieved successfully",
                "data": [dict(db_record) for db_record in db_records]
            }
    except Exception as e:
        print(f"Error while retrieving filters: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve filters") from e
    finally:
        db.close()


@settings.post('/delete_filter', response_model=DeleteFilterOutputSchema, tags=['Filters'])
def delete_filter(body: DeleteFilterInputSchema, db: psycopg2.extensions.connection = Depends(connect_db)):
    query = """
        DELETE FROM saved_filters
        WHERE id = %s
        RETURNING id, table_name, name
    """
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, (body.id,))  # Ensure `body.id` is passed as a tuple
            db_record = cursor.fetchone()

            # If no record is found for the given id, return a 404 error
            if not db_record:
                raise HTTPException(status_code=404, detail=f"Filter with id {body.id} not found")

            db.commit()  # Commit only if the record was successfully deleted
            return {
                "message": "Filter deleted successfully",
                "data": dict(db_record)
            }

    except psycopg2.Error as e:
        # Catching specific psycopg2 database errors for better diagnosis
        db.rollback()
        print(f"Database error while deleting filter: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred while deleting filter") from e

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions to avoid them being caught as generic exceptions
        raise http_exc

    except Exception as e:
        # Catching other unexpected errors
        db.rollback()
        print(f"Error while deleting filter: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete filter") from e

    finally:
        db.close()




@settings.post('/update_filters', response_model=SaveFiltersOutputSchema, tags=['Filters'])
def update_filters(body: UpdateFiltersInputSchema, db: psycopg2.extensions.connection = Depends(connect_db)):
    query = f"""
        UPDATE saved_filters
        SET filters = %s::jsonb, fields = %s::jsonb, name = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, user_id, filters, table_name, fields, name
    """

    values = (
        json.dumps(body.filters),  # Convert Python dict to JSON before insertion
        json.dumps(body.fields),  # Convert Python list to JSON before insertion
        body.name,
        body.id,
        body.user_id
    )

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, values)
            db_record = cursor.fetchone()
            db.commit()
            data = None
            if not db_record:
                message = "No filters found for the given id or permission denied"
            else:
                message = "Filters updated successfully"
                data = dict(db_record)
            return {
                "message": message,
                "data": data
            }
    except Exception as e:
        db.rollback()
        print(f"Error while updating filters: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update filters") from e
    finally:
        db.close()
    