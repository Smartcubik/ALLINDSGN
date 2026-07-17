from datetime import datetime, timedelta, timezone

TASHKENT_OFFSET = timedelta(hours=5)
TASHKENT_TZ = timezone(TASHKENT_OFFSET)


def now_tashkent() -> datetime:
    return datetime.now(timezone.utc).astimezone(TASHKENT_TZ)
