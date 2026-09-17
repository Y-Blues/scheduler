"""
Minimal 5-field cron expression parser and "next fire time" computation, pure and
dependency-free (see spec: no croniter, day-of-month/weekday combined with AND).
"""

from datetime import datetime, timedelta

_MAX_YEARS = 4


def next_fire_time(expression: str, after: datetime) -> datetime:
    """earliest minute-aligned datetime strictly after `after` matching expression
    ("minute hour day month weekday", weekday 0=Sunday..6=Saturday); ValueError if none
    is found within _MAX_YEARS years of `after`"""
    minutes, hours, days, months, weekdays = _parse(expression)
    candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    deadline = candidate.replace(year=candidate.year + _MAX_YEARS)

    while candidate < deadline:
        if candidate.month not in months:
            candidate = _first_of_next_month(candidate)
            continue
        if candidate.day not in days or _cron_weekday(candidate) not in weekdays:
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if candidate.hour not in hours:
            candidate = (candidate + timedelta(hours=1)).replace(minute=0)
            continue
        if candidate.minute not in minutes:
            candidate = candidate + timedelta(minutes=1)
            continue
        return candidate

    raise ValueError(f"no fire time for {expression!r} within {_MAX_YEARS} years of {after!r}")


def _cron_weekday(moment: datetime) -> int:
    return moment.isoweekday() % 7  # Monday=1..Saturday=6, Sunday=0


def _first_of_next_month(moment: datetime) -> datetime:
    if moment.month == 12:
        return moment.replace(year=moment.year + 1, month=1, day=1, hour=0, minute=0)
    return moment.replace(month=moment.month + 1, day=1, hour=0, minute=0)


def _parse(expression: str) -> tuple:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields (minute hour day month weekday), got {expression!r}")
    minute, hour, day, month, weekday = fields
    return (
        _parse_field(minute, 0, 59),
        _parse_field(hour, 0, 23),
        _parse_field(day, 1, 31),
        _parse_field(month, 1, 12),
        _parse_field(weekday, 0, 6),
    )


def _parse_field(field: str, low: int, high: int) -> set:
    values = set()
    for part in field.split(","):
        values |= _parse_part(part, low, high)
    return values


def _parse_part(part: str, low: int, high: int) -> set:
    range_part, _, step_text = part.partition("/")
    step = int(step_text) if step_text else 1
    if range_part == "*":
        start, end = low, high
    elif "-" in range_part:
        start_text, end_text = range_part.split("-")
        start, end = int(start_text), int(end_text)
    else:
        return {int(range_part)}
    return set(range(start, end + 1, step))
