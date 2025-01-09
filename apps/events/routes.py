from fastapi import APIRouter, HTTPException
from datetime import datetime
from opensearch import search_data, count
from key_mappings import mappings as field_mapping
from logger import logger
from apps.events.helpers import format_timeseries

events = APIRouter()

@events.post("/get_logs")
def get_logs(body:dict={}):
    page = body.get("page", 1)
    size = body.get("size", 10)
    filters = body.get("filters", {})
    order_by = body.get("sort", {})
    date_from = filters.pop("from")
    date_to = filters.pop("to")
    params = {
        "size": size,
        "from": size * (page - 1),
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "event.created": {
                                "gte": datetime.fromisoformat(date_from),
                                "lte": datetime.fromisoformat(date_to),
                            }
                        }
                    },
                ],
            }
        },
        "sort": {
            "event.created": {
                "order": "desc"
            }
        }
    }

    for k, v in filters.items():
        if v and k in field_mapping.keys():
            params["query"]["bool"]["must"].append({
                "match": {
                    field_mapping[k]: v
                }
            })
    
    for k, v in order_by.items():
        if k in field_mapping.keys():
            params["sort"][field_mapping[k]] = {
                "order": v or 'asc'
            }

    res = search_data(params)
    severity_count_params = {
        "size": 0,
        "query": params["query"],
        "aggs": {
            "by_severity": {
                "terms": {
                    "field": "event.severity.keyword",
                }
            }
        }
    }
    severity_res = search_data(severity_count_params)
    return {
        "total": res["hits"]["total"]["value"],
        "page": page,
        "size": size,
        "severity_count": {
            s["key"]: s["doc_count"]
            for s in severity_res["aggregations"]["by_severity"]["buckets"]
        },
        "records": [r['_source'] for r in res["hits"]["hits"]]
    }


@events.get("/get_logs/{id}")
def get_log(id:str):
    params = {
        "size": 1,
        "query": {
            "match": {
                "event.id":id
            },
        }
    }
    res = search_data(params)
    res = res["hits"]["hits"][0]["_source"]
    if res["event.id"] != id:
        raise HTTPException(status_code=404, detail="Item not found")
    return res


@events.get("/categories")
def categories():
    params = {
        "size": 0, 
        "aggs": {
            "unique_categories": {
                "terms": {
                    "field": "event.category.keyword",
                    "size": 100,
                }
            }
        }
    }
    res = search_data(params)
    cats = [
        b["key"] for b in
        res["aggregations"]["unique_categories"]["buckets"]
    ]
    print(res)
    return cats


@events.post("/get_countries_data")
def countries(body:dict={}):
    filters = body.get("filters", {})
    date_from = filters.get("from")
    date_to = filters.get("to")
    params = {
        "size": 0, 
        "aggs": {
            "unique_countries": {
                "terms": {
                    "field": "source.geo.country_name.keyword",
                    "size": 100,
                }
            }
        },
        "query": {
            "range": {
                "event.created": {
                }
            }
        }
    }
    if date_from:
        params["query"]["range"]["event.created"]["gte"] = datetime.fromisoformat(date_from)
    if date_to:
        params["query"]["range"]["event.created"]["lte"] = datetime.fromisoformat(date_to)

    res = search_data(params)
    countries = res["aggregations"]["unique_countries"]["buckets"]
    countries = filter(lambda x: x['key'], countries)
    countries = {
        d["key"]: d["doc_count"] for d in countries
    }
    return countries


@events.post('/get_charts_data')
def charts_data(body:dict={}):
    logger.debug(body)
    filters = body.get("filters", {})
    date_from = filters.get("from")
    date_to = filters.get("to")
    key = body.get("key", "severity")
    aggregation_name = f"time_v_{key}"
    params = {
        "size": 0,
        "query": {
            "range": {
                "event.created": {}
            }
        },
        "aggs": {
            aggregation_name: {
                "terms": {
                    "field": field_mapping[key],
                },
                "aggs": {
                    "timeline": {
                        "date_histogram": {
                            "field": "event.created",
                            "calendar_interval": "day",
                            "format": "YYYY-MM-dd",
                        },
                }
            },
            }
        }
    }
    if date_from:
        params["query"]["range"]["event.created"]["gte"] = datetime.fromisoformat(date_from)
    if date_to:
        params["query"]["range"]["event.created"]["lt"] = datetime.fromisoformat(date_to)
    res = search_data(params)
    response = {}
    for r in res['aggregations'][aggregation_name]['buckets']:
        tl = {}
        for t in r['timeline']['buckets']:
            tl[t['key_as_string']] = t['doc_count']
        response[r['key']] = tl
    return format_timeseries(response)


@events.post('/get_charts_data_all')
def timeline(body:dict={}):
    filters = body.get("filters", {})
    date_from = filters.get("from")
    date_to = filters.get("to")
    params = {
        "size": 0,
        "query": {
            "range": {
                "event.created": {}
            }
        },
        "aggs": {
            "events_over_time": {
                "date_histogram": {
                    "field": "event.created",
                    "calendar_interval": "day",
                    "format": "YYYY-MM-dd"
                },
                "aggs": {
                    "by_category": {
                        "terms": {
                            "field": "event.category.keyword"
                        },
                        "aggs": {
                            "countries": {
                                "terms": {
                                    "field": "source.geo.country_name.keyword"
                                },
                                "aggs": {
                                    "severity": {
                                        "terms": {
                                            "field": "event.severity.keyword"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if date_from:
        params["query"]["range"]["event.created"]["gte"] = datetime.fromisoformat(date_from)
    if date_to:
        params["query"]["range"]["event.created"]["lt"] = datetime.fromisoformat(date_to)
    
    res = search_data(params)
    response = {
        "raw": res,
        "timeseries": {},
        "severity": {
            "Medium": 0,
            "Low": 0,
            "High": 0
        },
    }

    data = res["aggregations"]["events_over_time"]["buckets"]
    events_total = 0
    for events_data in data:
        date = events_data["key_as_string"]
        response["timeseries"][date] = {
            "total": events_data["doc_count"]
        }
        events_total += events_data["doc_count"]
        for category in events_data["by_category"]["buckets"]:
            response["timeseries"][date][category["key"]] = {
                "total": category["doc_count"]
            }
            for country in category["countries"]["buckets"]:
                country_key = country["key"] or "Unknown"
                response["timeseries"][date][category["key"]][country_key] = {
                    "total": country["doc_count"]
                }
                for severity in country["severity"]["buckets"]:
                    response["timeseries"][date][category["key"]][country_key][severity["key"]] = {
                        "total": severity["doc_count"]
                    }
                    response["severity"][severity["key"]] += severity["doc_count"]

    response["total"] = events_total

    return response


@events.post('/snapshot')
def get_snapshot(body: dict={}):
    # Supports only opensearch for now. Add support for postgres soon.
    table_name = body.get("table")
    if not table_name:
        raise HTTPException(status_code=400, detail="Table name is required")
    
    filters = body.get("filters", {})
    params = {
        "query": {
            "bool": {
                "must": [],
            }
        }
    }

    date_from = filters.pop("from", None)
    date_to = filters.pop("to", None)

    if table_name == 'logs':
        if date_from or date_to:
            params["query"]["bool"]["must"].append({
                "range": {
                    "event.created": {
                    }
                }
            })
            if date_from:
                params["query"]["bool"]["must"][0]["range"]["event.created"]["gte"] = datetime.fromisoformat(date_from)
            if date_to:
                params["query"]["bool"]["must"][0]["range"]["event.created"]["lt"] = datetime.fromisoformat(date_to)
    
    for k, v in filters.items():
        params["query"]["bool"]["must"].append({
            "match": {
                k: v
            }
        })
    logger.debug(params)
    total_records = count(table_name, params)
    return {
        "total": total_records['count']
    }
