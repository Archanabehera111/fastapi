from database import connect_db

def res_to_config_format(res):
    data = {}
    try:
        for row in res:
            format_id = row[0]
            if format_id not in data:
                data[format_id] = {
                "id": format_id,
                "name": row[1],
                "user_id": row[2],
                "deleted": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "mappings": []
                }
            data[format_id]["mappings"].append({
            "id": row[6],
            "excel_field": row[7],
            "asset_field": row[8]
            })
    except Exception as e:
        print(e)
    return list(data.values())

def get_all_configs(body, db):
    # page = body.get("page", 1)
    # size = body.get("size", 10)
    filters = body.get("filters", body.get("filters", {}) )
    order_by = body.get("sort", {})

    try:
        query = '''
            SELECT
                aff.id as id,
                aff.name as name,
                aff.user_id as user_id,
                aff.deleted as deleted,
                aff.created_at as created_at,
                aff.updated_at as updated_at,
                ffm.id AS mapping_id,
                ffm.excel_field as excel_field,
                ffm.asset_field as asset_field
            FROM
                asset_file_formats aff
            INNER JOIN
                file_format_mappings ffm
            ON
                aff.id = ffm.format_id
            WHERE true
            AND deleted = false
        '''
        params = []
        f_query = ""

        for key, value in filters.items():
            f_query += f" AND {key} = %s"
            params.append(value)

        query += f_query
        
        # Handle sorting
        if order_by:
            sort_clauses = [f"{field} {direction}" for field, direction in order_by.items()]
            sort_clause = ", ".join(sort_clauses)
            query += f" ORDER BY {sort_clause}"

        # # Add pagination
        # query += " LIMIT %s OFFSET %s"
        # if size:
        #     params.extend([size, (page - 1) * size])

        print("query", query)
        with db.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchall()
        print("result", result)
        return result
    except Exception as e:
        print("Error while get configs ::", e)


def get_all_bu(db):
        query = '''
            select bu.id as bu_id, bu.name as bu_name, sbu.id as sbu_id, sbu.name as sbu_name, count(a.id) from assets a, bu, sbu where sbu.bu_id = bu.id and sbu.id = a.sbu_id group by 1, 2, 3, 4
        '''
        with db.cursor() as cur:
            cur.execute(query) 
            return cur.fetchall()


def res_to_bu_format(res):
    result = []
    sbu_dict = {}

    for item in res:
        id, name, sbu_id, sbu_name, count = item
        if id not in sbu_dict:
            sbu_dict[id] = {
                "id": id,
                "name": name,
                "value": 0,
                "sbu": []
            }
        sbu_dict[id]["sbu"].append({
            "id": sbu_id,
            "name": sbu_name,
            "value": count
        })
        sbu_dict[id]["value"] += count

    return list(sbu_dict.values())