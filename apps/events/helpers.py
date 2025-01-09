import datetime


def format_timeseries(data):
    all_dates = set()
    for category_data in data.values():
        all_dates.update(category_data.keys())

    # Step 2: Convert date strings to datetime objects
    date_format = "%Y-%m-%d"
    date_objs = [datetime.datetime.strptime(date_str, date_format) for date_str in all_dates]

    # Step 3: Find the earliest and latest dates
    min_date = min(date_objs)
    max_date = max(date_objs)

    # Step 4: Generate all dates between the earliest and latest dates
    total_days = (max_date - min_date).days + 1
    date_range = [min_date + datetime.timedelta(days=i) for i in range(total_days)]
    date_strings = [date_obj.strftime(date_format) for date_obj in date_range]

    # Step 5: Fill missing dates with 0 for each category
    for category in data:
        category_dates = data[category]
        for date_str in date_strings:
            category_dates.setdefault(date_str, 0)
        # Optional: Sort the dates
        data[category] = dict(sorted(category_dates.items(), key=lambda x: datetime.datetime.strptime(x[0], date_format)))

    return data
