from datetime import datetime, timedelta


def is_expired(deleted_at: datetime, now: datetime, days: int) -> bool:
    return now - deleted_at > timedelta(days=days)