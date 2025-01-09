from datetime import datetime
from opensearch import search_data, count
from fastapi import HTTPException
from logger import logger

date_fields = ["created_at", "updated_at", "resolved_at", "closed_at", "due_date", "start_date", "end_date", "event_start", "event_end"]
MAX_RESULT_WINDOW = 10_000

incident_columns = ['created_at', 'events', 'title', 'description', 'category', 'mitre_category', 'country', 'severity', 'priority', 'status', 'type', 'assigned_to', 'id', 'event_start', 'event_end', 'entity']

def get_incident(id: str):
    params = {
        "size": 1,
        "_source": incident_columns,
        "query": {
            "bool": {
                "must": [{
                    "match": {
                        "id.keyword": id
                    }
                }]
            }
        }
    }
    # Perform the search
    res = search_data(params, "incidents")
    
    # Check if a result was found
    if not res["hits"]["hits"]:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Return the found incident
    return res["hits"]["hits"][0]["_source"]

def fetch_all_incidents(body, incidents_index, incident_columns, action):
    # Extract pagination, filtering, and sorting details
    size = body.get("size", 0)
    page = body.get("page", 0)
    filters = body.get("filters", {})
    from_date = filters.pop("from", None)
    to_date = filters.pop("to", None)
    order_by = body.get("sort", {})

    # Base query structure
    query = {
        "bool": {
            "must": [
                {
                    "range": {
                        "created_at": {}
                    }
                }
            ]
        }
    }

    # Date filtering
    if from_date:
        query["bool"]["must"][0]["range"]["created_at"]["gte"] = datetime.isoformat(datetime.strptime(from_date, "%Y-%m-%d"))
    if to_date:
        query["bool"]["must"][0]["range"]["created_at"]["lt"] = datetime.isoformat(datetime.strptime(to_date, "%Y-%m-%d"))

    # Add filters to the query
    for k, v in filters.items():
        clause = {"terms" if isinstance(v, list) else "match": {f"{k}.keyword" if isinstance(v, list) else k: v}}
        query["bool"]["must"].append(clause)

    # Sort configuration
    sort = [
        {f"{k if k in date_fields else k+'.keyword'}": {"order": v or 'asc'}} for k, v in order_by.items()
    ]

    incident_params = {
        "query": query,
    }
    try:
        incident_count = count(incidents_index, incident_params)['count']
    except Exception as e:
        logger.error("eroorrrrr::", e)
        raise HTTPException(status_code=500, detail=str(e))

    sort_by = [{"created_at": "desc"},{"_id": "asc"}]
    sort_by.extend(sort)
    params = {
        "_source": incident_columns,
        "query": query,
        "sort": sort_by,
        "filters": filters,
        "page": page,
        "size": size,
        "from": size * (page - 1) if action != "download" and page else 0,
        "total_incidents": incident_count
    }

    logger.debug(params)
    logger.debug(incident_count)

    try:
        if not page:
            page = incident_count
        return fetch_records(incidents_index, params, action)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))
    
def fetch_records(index, params, action):
    results = []

    num_records = count(index)['count']
    end_at = params['from'] + params['size']
    if params['size'] == 0:
        end_at = params["total_incidents"]
        params['size'] = params["total_incidents"]
    total = 0
    
    # If the page is within the MAX_RESULT_WINDOW, we can fetch directly without pagination
    if end_at <= MAX_RESULT_WINDOW:
        body = {
            "_source": params["_source"],
            "sort": params["sort"],
            "size": params['size'],
            "from": params['from']
        }
        if params["query"]:
            body["query"] = params["query"]

        logger.debug(body)
        try:
            results = search_data(body, index)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        results = results['hits']['hits']
        total = params['total_incidents']
        
        result = {
            'hits': {
                'hits': [],
                'total': {
                    'value': 0
                },
                'size': 0

            }
        }

        result['hits']['hits'] = results
        result["hits"]["total"]["value"] = total
        result["hits"]["size"] = params["size"]
        return result

    # If the page is beyond MAX_RESULT_WINDOW, use deep pagination (search_after)
    start_record = params['from'] + 1
    end_record = start_record + params['size'] - 1
    if params["size"] == 0:
        end_record = params["total_incidents"]

    if end_record > num_records:
        end_record = num_records

    current_record = 1
    search_after = None

    fetch_size = 0


    while current_record <= end_record:
        fetch_size = min(MAX_RESULT_WINDOW, end_record - current_record + 1)

        if action == "search" and params["size"] > 0 and params["page"] > 0:
            current_search_record = 1
            fetch_search_size = 10000
            end_search_record = params["from"] + params["size"]
            search_done = False
            while current_search_record != end_search_record:
                
                query = {
                    "query": {
                        "match_all": {}
                    },
                    "size": fetch_search_size,
                    "sort": params["sort"]

                }

                if search_after:
                    query["search_after"] = search_after
                    query["from"] = 0

                logger.debug("search after 10000: %s", query)
                
                response = search_data(query, index)
                current_search_record += len(response['hits']['hits'])
                f_size = params["size"]
                if search_done:
                    break
                if current_search_record < params["from"]:
                    f_size = params["from"] - current_search_record + 1
                fetch_search_size = f_size if f_size < 10000 else 10000

                if len(response['hits']['hits']) > 0:
                    search_after = response['hits']['hits'][-1]['sort']

                if params["from"] <= current_search_record:
                    end_search_record = params["from"] + params["size"]
                    fetch_search_size = params["size"]
                    search_done = True

            if search_done:
                result = {
                    'hits': {
                        'hits': [],
                        'total': {
                            'value': 0
                        },
                        'size': 0
                    }
                }
                result['hits']['hits'] = response['hits']['hits']
                result["hits"]["total"]["value"] = params["total_incidents"]
                result["hits"]["size"] = params["size"]
                return result
        body = {
            # "_source": params["_source"],
            "sort": params["sort"],
            "size": fetch_size,
            "from": params['from']
        }

        if params["query"]:
            body["query"] = params["query"]

        if search_after:
            body["search_after"] = search_after

        logger.debug(body)
        response = search_data(body, index)

        hits = response['hits']['hits']
        total = total + fetch_size
        results.extend(hits)

        if len(hits) > 0:
            search_after = hits[-1]['sort']

        current_record += len(hits)

    result = {
        'hits': {
            'hits': [],
            'total': {
                'value': 0
            },
            'size': 0
        }
    }
    
    result['hits']['hits'] = results
    result["hits"]["total"]["value"] = total
    result["hits"]["size"] = params["size"]

    return result
    
# Function to split time range into equal segments and count objects in each segment
def split_timeframe_and_count(objects, num_segments=20):
    if not objects:
        return []
    
    if num_segments > len(objects):
        num_segments = len(objects)
    
    logger.debug(objects)
    timestamps = [obj['created_at'] for obj in objects]
    min_time = min(timestamps)
    max_time = max(timestamps)
    
    if min_time == max_time:
        # All timestamps are the same, return one segment with all objects
        return [{
            "start": min_time,
            "end": max_time,
            "count": len(objects),
            "events": [{
                "id": obj['id'],
                "created_at": obj['created_at'],
                "title": obj['rule'],
                "source_ip": obj['source_ip'],
            } for obj in objects]
        }]
    
    total_duration = max_time - min_time
    segment_duration = total_duration / num_segments
    
    segments = [(min_time + i * segment_duration, min_time + (i + 1) * segment_duration) for i in range(num_segments)]
    
    segment_counts = []
    for start, end in segments:
        events = [{
            "id": obj['id'],
            "created_at": obj['created_at'],
            "title": obj['rule'],
            "source_ip": obj['source_ip'],
        } for obj in objects if start <= obj['created_at'] < end]
        segment_counts.append({
            "start": start,
            "end": end,
            "count": len(events),
            "events": events
        })
    
    # Handle edge case where max timestamp falls exactly on the final segment end
    events = [{
        "id": obj['id'],
        "created_at": obj['created_at'],
        "title": obj['rule'],
        "source_ip": obj['source_ip'],
    } for obj in objects if segment_counts[-1]["start"] <= obj['created_at'] <= segment_counts[-1]["end"]]
    segment_counts[-1]["events"] = events
    segment_counts[-1]["count"] = len(events)
    
    return segment_counts

