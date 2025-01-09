from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from key_mappings import mappings as field_mapping
from opensearch import search_data, count
from logger import logger
from apps.incidents.schema import TimelineInputSchema, GetEventsSchema
from apps.incidents.schema import IncidentRequest, IncidentResponseSchema, IncidentMitigationRequestSchema, IncidentMitigationResponseSchema
from apps.incidents.notes.routes import notes
from apps.incidents.helpers import fetch_all_incidents, split_timeframe_and_count, get_incident
import pandas as pd
from io import BytesIO
import json

incidents = APIRouter()

incidents.include_router(notes, prefix='/notes', tags=['Notes'])

incidents_index = "incidents"
incident_columns = ['created_at', 'events', 'title', 'description', 'category', 'mitre_category', 'country', 'severity', 'priority', 'status', 'type', 'assigned_to', 'id', 'event_start', 'event_end', 'entity']



@incidents.get('/{id}')
async def get_incident_by_id(id: str):
    return get_incident(id)


@incidents.post('/search')
async def get_incidents(body: dict = {}):
    # Handle empty payload
    if not body:
        body = {
            "page": 1,
            "size": 10,
            "filters": {},  # Default filters, can be customized
        }
    
    # Execute the search query
    try:
        res = fetch_all_incidents(body, incidents_index, incident_columns, "search")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Return the search results
    return {
        "total": res["hits"]["total"]["value"],
        "page": body.get("page", 1),
        "size": body.get("size", 10),
        "records": [r['_source'] for r in res["hits"]["hits"]]
    }


@incidents.post("/aggregate")
async def get_aggregate(body: dict = {}):
    filters = body.get("filters", {})
    key = body.get("key", None)
    date_from = filters.pop("from", None)
    date_to = filters.pop("to", None)

    if not key:
        raise HTTPException(status_code=400, detail="Key is mandatory.")

    params = {
        "size": 0,
        "query": {
            "bool": {
                "must": [{
                    "range": {
                        "created_at": {}
                    }
                }]
            }
        },
        "aggs": {
            "aggregation_result": {
                "terms": {
                    "field": f"{key}.keyword",
                    "size": 500
                }
            }
        }
    }

    if date_from:
        params["query"]["bool"]["must"][0]["range"]["created_at"]["gte"] = datetime.fromisoformat(date_from)

    if date_to:
        params["query"]["bool"]["must"][0]["range"]["created_at"]["lt"] = datetime.fromisoformat(date_to)

    # Add filters to the query
    for k, v in filters.items():
        if isinstance(v, list):
            # Use "should" query for multiple values
            params["query"]["bool"]["must"].append({
                "terms": {
                    f"{k}.keyword": v
                }
            })
        else:
            # Use "match" query for a single value
            params["query"]["bool"]["must"].append({
                "match": {
                    k: v
                }
            })

    logger.debug(params)
    # Execute the aggregation query
    try:
        res = search_data(params, incidents_index)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Process the aggregation results
    buckets = res["aggregations"]["aggregation_result"]["buckets"]
    return {bucket["key"] if bucket["key"] else 'Unknown': bucket["doc_count"] for bucket in buckets}


@incidents.post("/timeline")
async def get_timeline(body: TimelineInputSchema):
    filters = body.filters
    date_from = filters.get("from")
    date_to = filters.get("to")
    key = body.key
    aggregation_name = f"time_v_{key}"
    params = {
        "size": 0,
        "query": {
            "range": {
                "created_at": {}
            }
        },
        "aggs": {
            aggregation_name: {
                "terms": {
                    "field": f"{key}.keyword",
                },
                "aggs": {
                    "timeline": {
                        "date_histogram": {
                            "field": "created_at",
                            "calendar_interval": "day",
                            "format": "YYYY-MM-dd",
                        },
                }
            },
            }
        }
    }
    if date_from:
        params["query"]["range"]["created_at"]["gte"] = datetime.fromisoformat(date_from)
    if date_to:
        params["query"]["range"]["created_at"]["lt"] = datetime.fromisoformat(date_to)
    logger.debug(params)
    res = search_data(params, incidents_index)
    response = {}
    for r in res['aggregations'][aggregation_name]['buckets']:
        tl = {}
        for t in r['timeline']['buckets']:
            tl[t['key_as_string']] = t['doc_count']
        response[r['key']] = tl
    return {
        "message": "Success",
        "data": response
    }


@incidents.post("/events_incidents_ratio")
async def get_events_incidents_ratio(body: dict = {}):
    filters = body.get("filters", {})
    date_from = filters.pop("from", None)
    date_to = filters.pop("to", None)

    logs_params = {
        "query": {
            "bool": {
                "must": []
            }
        }
    }

    incident_params = {
        "query": {
            "bool": {
                "must": []
            }
        }
    }

    if date_from or date_to:
        range_clause_logs = {"range": {}}
        range_clause_incident = {"range": {}}

        if date_from:
            range_clause_logs["range"]["event.created"] = {"gte": datetime.fromisoformat(date_from).isoformat()}
            range_clause_incident["range"]["created_at"] = {"gte": datetime.fromisoformat(date_from).isoformat()}

        if date_to:
            range_clause_logs["range"]["event.created"] = range_clause_logs["range"].get("event.created", {})
            range_clause_logs["range"]["event.created"]["lte"] = datetime.fromisoformat(date_to).isoformat()
            range_clause_incident["range"]["created_at"] = range_clause_incident["range"].get("created_at", {})
            range_clause_incident["range"]["created_at"]["lte"] = datetime.fromisoformat(date_to).isoformat()

        # Add range clauses to params
        if range_clause_logs["range"]:
            logs_params["query"]["bool"]["must"].append(range_clause_logs)
        if range_clause_incident["range"]:
            incident_params["query"]["bool"]["must"].append(range_clause_incident)

    for k, v in filters.items():
        if v and k in field_mapping:
            match_clause = {
                "match": {
                    field_mapping[k]: v
                }
            }
            logs_params["query"]["bool"]["must"].append(match_clause)
            incident_params["query"]["bool"]["must"].append(match_clause)

    # Execute the aggregation query
    try:
        incident_result = count('incidents', incident_params)
        incident_count = incident_result["count"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    try:
        logs_result = count('logs', logs_params)
        events_count = logs_result["count"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    event_ratio = "NA"
    try:
        incident_event_ratio = events_count/incident_count
        event_ratio = "NA" if incident_event_ratio <= 0 else f"""{round(incident_event_ratio, 2)} : 1"""

    except ZeroDivisionError:
        incident_event_ratio = 0

    # Process the aggregation results
    response = {
        "message": "Data fetched sucessfully",
        "data": {"no_events" : events_count, "no_incidents" : incident_count, "incident_event_ratio" : event_ratio}
    }
    return response


@incidents.post("/mitigations", response_model=IncidentMitigationResponseSchema)
async def get_mitigations(body: IncidentMitigationRequestSchema):
    incident_id = body.incident_id

    params = {
        "size": 1,
        "query": {
            "bool": {
                "must": [{
                    "terms": {
                        "incident_id.keyword": [incident_id]
                    }
                }]
            }
        }
    }
    try:
        res = search_data(params, 'mitigations')
        data = []
        if res["hits"]["total"]["value"] == 0:
            message = "No mitigations found"
        else:
            data = res["hits"]["hits"][0]['_source'].get('mitigations', [])
            message = "Data fetched successfully"

        return {
            "message": message,
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@incidents.post("/events")
def get_event_details(body: GetEventsSchema):
    incident_id = body.incident_id
    params = {
        "size": 1,
        "_source": ["id", "events"],
        "query": {
            "bool": {
                "must": [{
                    "terms": {
                        "id.keyword": [incident_id]
                    }
                }]
            }
        }
    }
    logger.debug(params)
    res = search_data(params, incidents_index)
    logger.debug(res)

    if res["hits"]["total"]["value"] == 0:
        return {
            "message": "No data found",
            "data": []
        }

    event_ids = res["hits"]["hits"][0]['_source']['events']

    events_params = {
        "size": len(event_ids),
        "_source": ["event.id", "event.created", "rule.name", "source.ip"],
        "query": {
            "bool": {
                "must": [{
                    "terms": {
                        "event.id.keyword": event_ids
                    }
                }]
            }
        },
        "sort": [
            {
                "event.created": {
                    "order": body.sort
                }
            }
        ]
    }
    logger.debug("Event Params: ")
    logger.debug(json.dumps(events_params))
    events = search_data(events_params, "logs")

    return {
        "message": "Data fetched successfully",
        "data": [{
            "id": event["_source"]["event.id"],
            "created_at": event["_source"]["event.created"],
            "rule": event["_source"]["rule.name"],
            "source_ip": event["_source"]["source.ip"]
        } for event in events["hits"]["hits"]]
    }


@incidents.post("/events_distribution")
def get_events_distribution(body: GetEventsSchema):
    body.sort = "asc"
    data = get_event_details(body)["data"]
    for item in data:
        item["created_at"] = datetime.fromisoformat(item["created_at"])
    res = split_timeframe_and_count(data)
    return {
        "message": "Data fetched successfully",
        "data": res
    }


@incidents.post("/related", response_model=IncidentResponseSchema)
async def get_related_incidents(request: IncidentRequest):
    try:

        # incident = get_incident(request.incidentId)
        # logger.debug(incident)
        # params = {
        #     "size": 5,
        #     "_source": ["id", "title", "category", "created_at"],
        #     "query": {
        #         "bool": {
        #             "must": [
        #                 {"terms": {"category.keyword": [incident["category"]]}},
        #             ],
        #             "must_not": [
        #                 {
        #                     "terms": {
        #                         "id.keyword": [request.incidentId]
        #                     }
        #                 }
        #             ]
        #         }
        #     },
        #     "sort": [{
        #         "created_at": "desc"
        #     }]
        # }
        # logger.debug(json.dumps(params))


        # Search query for OpenSearch to find the given incident
        query = {
            "query": {
                "bool": {
                    "must": [{
                        "terms": {
                            "incident_id.keyword": [request.incident_id]
                        }
                    }]
                }
            }
        }
        logger.debug(query)
        # Perform the search on OpenSearch
        response = search_data(query, index_name="related_incidents")

        logger.debug(response)

        # Check if the incident exists
        if len(response["hits"]["hits"]) == 0:
            incident = get_incident(request.incident_id)
            logger.debug(incident)
            params = {
                "size": 5,
                "_source": ["id", "title", "category", "created_at", "source_ip"],
                "query": {
                    "bool": {
                        "must": [
                            {"terms": {"source_ip.keyword": [incident["source_ip"]]}},
                        ],
                        "must_not": [
                            {
                                "terms": {
                                    "id.keyword": [request.incident_id]
                                }
                            }
                        ]
                    }
                },
                "sort": [{
                    "created_at": "desc"
                }]
            }
            logger.debug(json.dumps(params))
            return {
                "message": "Success",
                "data": [hit['_source'] for hit in search_data(params, incidents_index)["hits"]["hits"]]
            }

        # Get the related incidents from the response
        related_incidents = response["hits"]["hits"][0]["_source"].get("related_incidents")
        if related_incidents is not None:
            
            # Now, search for the related incidents
            related_incidents_query = {
                "_source": ["id", "title", "category", "created_at", "source_ip"],
                "query": {
                    "terms": {
                        "id.keyword": related_incidents
                    }
                },
                "sort": [
                    {"created_at": "desc"}
                ]
            }

            # Perform the search on OpenSearch for the related incidents
            related_response = search_data(related_incidents_query, index_name="incidents")

            # Debugging logs (inspect the response from the related incidents search)
            logger.debug(f"Related incidents search response: {related_response}")

            # Prepare the response data
            related_data = [
                hit['_source']
                for hit in related_response["hits"]["hits"]
            ]
            return {
                "message": "Success",
                "data": related_data
            }
        else:
            return {
                "message": "No related incidents found..",
                "data": []
            }
        

    except Exception as e:
        # Log the exception and raise a generic 500 error
        logger.error(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@incidents.post("/download")
def download_incidents(body: dict={}):
    download_columns = body.get("download_columns", [])
    name = body.get("filename", None)

    if not len(download_columns) and len(incident_columns):
        download_columns = incident_columns

    try:
        res = fetch_all_incidents(body, incidents_index, download_columns, "download")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    results = res['hits']['hits']
    ordered_results = [
        {key: hit['_source'].get(key) for key in download_columns}
        for hit in results
    ]

    query_result = json.loads(json.dumps(ordered_results))

    df = pd.DataFrame(query_result)[download_columns]

    output = BytesIO()
    df.to_excel( output, index=False, engine="openpyxl" )
    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if name is None:
        download_filename = f"incidents_{timestamp}"
    else:
        download_filename = f"{name}_{timestamp}"

    response = StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={download_filename}.xlsx"}
    )

    return response
