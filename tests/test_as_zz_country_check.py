from datetime import timezone

from ixp_tracker.ixp_tracker import as_zz_country_check
from tests.fixtures import MockLookup


def test_as_not_registered_to_zz_returns_false(faker):
    asn = faker.random_number(digits=5)
    as_at = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    assert as_zz_country_check(asn, as_at, MockLookup(default_country="US")) is False


def test_as_registered_to_zz_and_not_assigned_returns_true(faker):
    asn = faker.random_number(digits=5)
    as_at = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    assert as_zz_country_check(
        asn, as_at, MockLookup(default_country="ZZ", default_status="reserved")
    )


def test_as_registered_to_zz_but_assigned_returns_false(faker):
    asn = faker.random_number(digits=5)
    as_at = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    assert (
        as_zz_country_check(
            asn, as_at, MockLookup(default_country="ZZ", default_status="assigned")
        )
        is False
    )


def test_as112_returns_false(faker):
    asn = 112
    as_at = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    assert as_zz_country_check(asn, as_at, MockLookup(default_country="ZZ")) is False
