from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from ixp_tracker.models import StatsPerCountry
from ixp_tracker.stats import generate_stats
from tests.test_ixp_stats import create_member_fixture
from tests.test_members_import import create_ixp_fixture

pytestmark = pytest.mark.django_db


class TestLookup:

    def __init__(self, default_status: str = "assigned"):
        self.default_status = default_status

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass

    def get_asns_for_country(self, country: str, as_at: datetime) -> List[int]:
        return [12345, 446, 789, 5050, 54321]

    def get_routed_asns_for_country(self, country: str, as_at: datetime) -> List[int]:
        return [12345, 446, 789, 54321]


def test_with_no_data_generates_no_stats():
    generate_stats(TestLookup())

    stats = StatsPerCountry.objects.all()
    assert len(stats) == 249
    first_stat = stats.first()
    assert first_stat.member_count == 0


def test_generates_stats():
    ixp_one = create_ixp_fixture(123, "CH")
    create_member_fixture(ixp_one, 12345, 500)
    create_member_fixture(ixp_one, 67890, 10000)
    ixp_two = create_ixp_fixture(124, "CH")
    create_member_fixture(ixp_two, 5050, 6000)
    create_member_fixture(ixp_two, 67890, 10000)

    generate_stats(TestLookup())

    stats = StatsPerCountry.objects.filter(country_code="CH").first()
    # The default fixture does not have a recent last_active date so technically they shouldn't be counted here
    assert stats.ixp_count == 2
    assert stats.asn_count == 5
    assert stats.routed_asn_count == 4
    assert stats.member_count == 3
    assert stats.total_capacity == 26.5
    assert stats.asns_ixp_member_rate == 0.4
    assert stats.routed_asns_ixp_member_rate == 0.25


def test_generates_ixp_counts():
    stats_date = (datetime.now(timezone.utc) - timedelta(weeks=16)).replace(day=1)
    one_month_before = (stats_date - timedelta(days=1)).replace(day=1)
    one_month_after = (stats_date - timedelta(days=35)).replace(day=1)
    # currently_active member
    active = create_ixp_fixture(123, "CH")
    create_member_fixture(active, 12345, 500, member_since=one_month_before, date_left=one_month_after)
    # member active in the past
    member_in_past = create_ixp_fixture(124, "CH")
    create_member_fixture(member_in_past, 12345, 500, member_since=one_month_before, date_left=one_month_before)
    # member not yet active (as we are generating historical stats there could be members in the future)
    mmeber_in_future = create_ixp_fixture(125, "CH")
    create_member_fixture(mmeber_in_future, 12345, 500, member_since=one_month_after, date_left=None)

    generate_stats(TestLookup())

    stats = StatsPerCountry.objects.filter(country_code="CH").first()
    assert stats.ixp_count == 1


def test_handles_invalid_country():
    create_ixp_fixture(123, "XK")

    generate_stats(TestLookup())

    country_stats = StatsPerCountry.objects.filter(country_code="XK").first()
    assert country_stats is None
