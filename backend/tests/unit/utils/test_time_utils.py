from datetime import timedelta

from app.utils.time import coerce_datetime, utc_now


def test_coerce_datetime_parses_z_suffix():
    dt = coerce_datetime("2026-01-01T00:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)
    assert dt.isoformat().endswith("+00:00")


def test_coerce_datetime_parses_offset():
    dt = coerce_datetime("2026-01-01T02:00:00+02:00")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)
    assert dt.hour == 0


def test_coerce_datetime_parses_naive_as_utc():
    dt = coerce_datetime("2026-01-01T00:00:00")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)

    time_diff = utc_now() - dt
    assert isinstance(time_diff, timedelta)
