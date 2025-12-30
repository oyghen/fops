import datetime as dt


def utctimestamp() -> str:
    """Return UTC timestamp string."""
    return dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
