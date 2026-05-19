from datetime import datetime, timezone, timedelta


from ixp_tracker.ixp_tracker import stringify_date


def test_returns_expected_string_format():
    test_date = datetime(2019, 1, 1, tzinfo=timezone.utc)

    date_string = stringify_date(test_date)

    assert date_string == "2019-01-01 00:00:00+0000"


def test_strips_microseconds():
    test_date = datetime(2019, 1, 1, microsecond=123, tzinfo=timezone.utc)

    date_string = stringify_date(test_date)

    assert date_string == "2019-01-01 00:00:00+0000"


def test_preserves_existing_timezone():
    test_date = datetime(
        2019, 1, 1, microsecond=123, tzinfo=timezone(timedelta(hours=1))
    )

    date_string = stringify_date(test_date)

    assert date_string == "2019-01-01 00:00:00+0100"


def test_adds_timezone_if_needed():
    test_date = datetime(2019, 1, 1, microsecond=123)

    date_string = stringify_date(test_date)

    assert date_string == "2019-01-01 00:00:00+0000"
