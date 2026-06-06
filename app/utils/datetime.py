from datetime import datetime
from zoneinfo import ZoneInfo

# Cache timezone info to avoid repeated lookups
_cached_tz = None


def _get_server_timezone():
    """Get server timezone, cached on first call."""
    global _cached_tz
    if _cached_tz is not None:
        return _cached_tz

    try:
        # Try to get local timezone from the system
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz:
            _cached_tz = local_tz
            return _cached_tz
    except Exception:
        pass

    # Default to Shanghai timezone (UTC+8)
    _cached_tz = ZoneInfo("Asia/Shanghai")
    return _cached_tz


def utcnow() -> datetime:
    """Get current datetime with server timezone, default to Shanghai."""
    tz = _get_server_timezone()
    return datetime.now(tz)
