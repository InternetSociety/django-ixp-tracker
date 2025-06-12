from datetime import datetime, timezone
from typing import List

import pytest

from ixp_tracker.models import IXPMember, IXPMembershipRecord, StatsPerIXP
from ixp_tracker.stats import calculate_local_asns_members_rate, generate_stats
from tests.test_members_import import create_asn_fixture, create_ixp_fixture

pytestmark = pytest.mark.django_db

class TestLookup:
    __test__ = False

    def __init__(self, default_status: str = "assigned"):
        self.default_status = default_status

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass

    def get_asns_for_country(self, country: str, as_at: datetime) -> List[int]:
        return [12345, 446, 789, 5050, 54321]

    def get_routed_asns_for_country(self, country: str, as_at: datetime) -> List[int]:
        return [12345, 446, 789]


def test_with_no_data_generates_no_stats():
    generate_stats(TestLookup())

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 0


def test_generates_capacity_rs_peering_and_member_count():
    ixp = create_ixp_fixture(123)
    create_member_fixture(ixp, 12345, 500, True)
    create_member_fixture(ixp, 67890, 10000)

    generate_stats(TestLookup())

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 1
    ixp_stats = stats.first()
    assert ixp_stats.members == 2
    assert ixp_stats.capacity == 10.5
    assert ixp_stats.rs_peering_rate == 0.5


def test_generates_stats_for_first_of_month():
    create_ixp_fixture(123)

    generate_stats(TestLookup(), datetime(year=2024, month=2, day=10, tzinfo=timezone.utc))

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 1
    ixp_stats = stats.first()
    assert ixp_stats.stats_date == datetime(year=2024, month=2, day=1).date()


def test_does_not_count_members_marked_as_left():
    ixp = create_ixp_fixture(123)
    create_member_fixture(ixp, 12345, 500)
    create_member_fixture(ixp, 67890, 10000, True, datetime(year=2024, month=4, day=1, tzinfo=timezone.utc))

    generate_stats(TestLookup())

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1
    assert ixp_stats.capacity == 0.5
    assert ixp_stats.rs_peering_rate == 0


def test_does_not_count_member_twice_if_they_rejoin():
    ixp = create_ixp_fixture(123)
    member = create_member_fixture(ixp, 67890, 10000, False, datetime(year=2024, month=4, day=1, tzinfo=timezone.utc))
    membership = IXPMembershipRecord(
        member=member,
        start_date=datetime(year=2024, month=5, day=1),
        is_rs_peer=False,
        speed=5000,
        end_date=None
    )
    membership.save()

    generate_stats(TestLookup())

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1


def test_does_not_count_members_not_yet_created():
    ixp = create_ixp_fixture(123)
    create_member_fixture(ixp, 12345, 500, True, member_since=datetime(year=2024, month=1, day=1).date())
    create_member_fixture(ixp, 67890, 10000, False, member_since=datetime(year=2024, month=4, day=1).date())

    generate_stats(TestLookup(), datetime(year=2024, month=2, day=1, tzinfo=timezone.utc))

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1
    assert ixp_stats.capacity == 0.5
    assert ixp_stats.rs_peering_rate == 1


def test_does_not_count_ixps_not_yet_created():
    ixp = create_ixp_fixture(123)
    ixp.created = datetime(year=2024, month=4, day=1, tzinfo=timezone.utc)
    ixp.save()
    create_member_fixture(ixp, 12345, 500)
    create_member_fixture(ixp, 67890, 10000)

    generate_stats(TestLookup(), datetime(year=2024, month=2, day=1, tzinfo=timezone.utc))

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats is None


def test_saves_local_asns_members_rate():
    ixp_one = create_ixp_fixture(123, "CH")
    create_member_fixture(ixp_one, 12345, 500, asn_country="CH")
    create_member_fixture(ixp_one, 67890, 10000, asn_country="CH")
    ixp_two = create_ixp_fixture(456, "CH")
    create_member_fixture(ixp_two, 54321, 500, asn_country="CH")
    create_member_fixture(ixp_two, 9876, 10000, asn_country="CH")

    generate_stats(TestLookup())

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.local_asns_members_rate == 0.2


def test_saves_local_routed_asns_members_rate():
    ixp_one = create_ixp_fixture(123, "CH")
    create_member_fixture(ixp_one, 12345, 500, asn_country="CH")
    create_member_fixture(ixp_one, 67890, 10000, asn_country="CH")
    ixp_two = create_ixp_fixture(456, "CH")
    create_member_fixture(ixp_two, 54321, 500, asn_country="CH")
    create_member_fixture(ixp_two, 9876, 10000, asn_country="CH")

    generate_stats(TestLookup())

    ixp_stats = StatsPerIXP.objects.all().first()
    assert pytest.approx(ixp_stats.local_routed_asns_members_rate, 0.01) == 0.33


def test_calculate_local_asns_members_rate_returns_zero_if_no_asns_in_country():
    rate = calculate_local_asns_members_rate([12345], [])

    assert rate == 0


def test_calculate_local_asns_members_rate():
    rate = calculate_local_asns_members_rate([12345], [12345, 446, 789, 5050, 54321])

    assert rate == 0.2


def test_calculate_local_asns_members_rate_ignores_members_not_in_country_list():
    rate = calculate_local_asns_members_rate([12345, 789], [12345, 446, 5050, 54321])

    assert rate == 0.25


def create_member_fixture(ixp, as_number, speed, is_rs_peer = False, date_left = None, member_since = None, asn_country = "CH"):
    last_active = date_left or datetime.now(timezone.utc)
    member_since = member_since or datetime(year=2024, month=4, day=1).date()
    asn = create_asn_fixture(as_number, asn_country)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=datetime.now(timezone.utc),
        last_active=last_active
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=member_since,
        is_rs_peer=is_rs_peer,
        speed=speed,
        end_date=date_left
    )
    membership.save()
    return member
