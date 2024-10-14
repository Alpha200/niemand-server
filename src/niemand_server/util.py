from datetime import datetime, date
from humanize import naturalday


def format_date(dt: datetime | date):
    if isinstance(dt, datetime):
        return f"{naturalday(dt.astimezone())} {dt.astimezone().strftime('%H:%M')}"
    else:
        return naturalday(dt)
