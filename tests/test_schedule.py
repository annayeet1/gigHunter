from datetime import datetime, time
from zoneinfo import ZoneInfo

from gighunter.schedule import Schedule, is_due

CT = ZoneInfo("America/Chicago")
S = Schedule(send_time=time(9, 0), early_minutes=10, catch_up_minutes=120)


def at(y, m, d, hh, mm, tz=CT):
    return datetime(y, m, d, hh, mm, tzinfo=tz)


def test_due_in_window():
    assert is_due(S, at(2026, 11, 17, 8, 55), None)[0]        # 8:55 run, 5 min early
    assert is_due(S, at(2026, 11, 17, 10, 55), None)[0]       # catch-up
    assert not is_due(S, at(2026, 11, 17, 8, 45), None)[0]    # too early
    assert not is_due(S, at(2026, 11, 17, 11, 5), None)[0]    # too late


def test_once_per_day():
    assert not is_due(S, at(2026, 11, 17, 9, 55), "2026-11-17")[0]
    assert is_due(S, at(2026, 11, 18, 8, 55), "2026-11-17")[0]


def test_days_and_disabled():
    weekdays = Schedule(days=("Mon", "Tue", "Wed", "Thu", "Fri"))
    assert not is_due(weekdays, at(2026, 11, 21, 9, 0), None)[0]   # Saturday
    assert not is_due(Schedule(enabled=False), at(2026, 11, 17, 9, 0), None)[0]


def test_dst_handled_from_utc_clock():
    utc = ZoneInfo("UTC")
    assert is_due(S, at(2026, 7, 14, 13, 55, utc), None)[0]   # 8:55 CDT (summer)
    assert is_due(S, at(2026, 12, 15, 14, 55, utc), None)[0]  # 8:55 CST (winter)
