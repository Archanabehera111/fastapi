from fastapi import APIRouter, HTTPException
from apps.incidents.notes.schemas import *
from opensearch import index_data, search_data, client
from apps.incidents.helpers import get_incident
from uuid import uuid4
from datetime import datetime
from logger import logger
import json

notes = APIRouter()
notes_index = "incident_notes"


@notes.post("/add", response_model=NoteResponseSchema)
def add_a_note_to_incident(body: NoteInputSchema):

    if not body.incident_id:
        raise HTTPException(status_code=400, detail="incident_id is mandatory.")
    if not body.user_id:
        raise HTTPException(status_code=400, detail="user_id is mandatory.")
    if not body.note:
        raise HTTPException(status_code=400, detail="note is mandatory.")
    
    try:
        get_incident(body.incident_id)
        doc = {
            "id": str(uuid4()),
            "incident_id": body.incident_id,
            "user_id": body.user_id,
            "note": body.note,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "history": [],
            "deleted": False
        }
        index_data(notes_index, doc)
        return {
            "message": "Note added succesfully!",
            "data": doc
        }
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        
@notes.post("/get", response_model=NoteResponseSchema)
def get_all_notes_by_incident_id(body: GetNotesInputSchema):
    try:
        query = {
            "size": 1000,
            "query": {
                "bool": {
                    "must": [{
                        "terms": {
                            "incident_id.keyword": [body.incident_id]
                        }
                    }, {
                        "term": {
                            "deleted": False
                        }
                    }]
                }
            },
            "sort": [{
                "created_at": "desc"
            }]
        }

        get_incident(body.incident_id)
        results = search_data(query, notes_index)
        return {
            "message": "Notes retrieved successfully!",
            "data": [hit['_source'] for hit in  results['hits']['hits']]
        }
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@notes.post("/update", response_model=NoteResponseSchema)
def update_a_note_by_id(body: NoteUpdateInputSchema):
    try:
        query = {
            "size": 1,
            "query": {
                "bool": {
                    "must": [{
                        "terms": {
                            "id.keyword": [body.id]
                        }
                    }, {
                        "terms": {
                            "user_id.keyword": [body.user_id]
                        }
                    }]
                }
            }
        }
        result = search_data(query, notes_index)
        if result['hits']['total']['value'] == 0:
            raise HTTPException(
                status_code=404,
                detail="Note not found or permission denied!"
            )

        _note = result['hits']['hits'][0]['_source']
        if body.note == _note['note']:
            return {
                "message": "No update!",
                "data": _note
            }
        _note['history'].append({'updated_at': _note['updated_at'], 'value': _note['note']})
        _note['note'] = body.note

        update_query = {
            "script": {
                "source": """
                    ctx._source.note = params.note;
                    ctx._source.updated_at = params.updated_at;
                    ctx._source.history = params.history;
                """,
                "lang": "painless",
                "params": {
                    "note": body.note,
                    "updated_at": datetime.now().isoformat(),
                    "history": _note['history'],
                }
            },
            "query": {
                "bool": {
                    "must": [{
                        "terms": {
                            "id.keyword": [_note['id']]
                        }
                    }]
                }
            }
        }
        client.update_by_query(
            index=notes_index,
            body=json.dumps(update_query)
        )
        
        return {
            "message": "Note updated successfully!",
            "data": _note
        }
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@notes.post("/delete", response_model=NoteDeleteResponseSchema)
def delete_note(body: NoteDeleteInputSchema):
    try:
        query = {
            "size": 1,
            "query": {
                "bool": {
                    "must": [{
                        "terms": {
                            "id.keyword": [body.id]
                        }
                    }, {
                        "terms": {
                            "user_id.keyword": [body.user_id]
                        }
                    }]
                }
            }
        }
        result = search_data(query, notes_index)
        if result['hits']['total']['value'] == 0:
            raise HTTPException(
                status_code=404,
                detail="Note not found or permission denied!"
            )

        _note = result['hits']['hits'][0]['_source']
        update_query = {
            "script": {
                "source": """
                    ctx._source.deleted = true;
                """,
                "lang": "painless"
            },
            "query": {
                "bool": {
                    "must": [{
                        "terms": {
                            "id.keyword": [_note['id']]
                        }
                    }]
                }
            }
        }
        client.update_by_query(
            index=notes_index,
            body=json.dumps(update_query)
        )
        
        return {
            "message": "Note deleted successfully!",
            "data": None
        }
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
