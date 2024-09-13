from datetime import datetime
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
    assert stats.asn_count == 5
    assert stats.member_count == 3
    assert stats.total_capacity == 26.5
    assert stats.asns_ixp_member_rate == 0.4


def test_handles_invalid_country():
    create_ixp_fixture(123, "XK")

    generate_stats(TestLookup())

    country_stats = StatsPerCountry.objects.filter(country_code="XK").first()
    assert country_stats is None
