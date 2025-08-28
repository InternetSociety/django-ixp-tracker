from datetime import datetime, timedelta, timezone

import pytest

from ixp_tracker.models import StatsPerIXP
from ixp_tracker.stats import calculate_local_asns_members_rate, generate_stats
from tests.fixtures import ASNFactory, IXPFactory, IXPMembershipRecordFactory, MockLookup, StatsPerIXPFactory, \
    create_member_fixture

pytestmark = pytest.mark.django_db


def test_with_no_data_generates_no_stats():
    generate_stats(MockLookup())

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 0


def test_generates_capacity_rs_peering_and_member_count():
    ixp = IXPFactory()
    create_member_fixture(ixp, membership_properties={"speed": 500, "is_rs_peer": True})
    create_member_fixture(ixp, membership_properties={"speed": 10000, "is_rs_peer": False})

    generate_stats(MockLookup())

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 1
    ixp_stats = stats.first()
    assert ixp_stats.members == 2
    assert ixp_stats.capacity == 10.5
    assert ixp_stats.rs_peering_rate == 0.5


def test_generates_stats_for_first_of_month():
    IXPFactory()

    stats_date = datetime.now(timezone.utc).replace(day=10)
    generate_stats(MockLookup(), stats_date)

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 1
    ixp_stats = stats.first()
    assert ixp_stats.stats_date == stats_date.replace(day=1).date()


def test_does_not_count_members_marked_as_left():
    ixp = IXPFactory()
    create_member_fixture(ixp, membership_properties={"speed": 500, "is_rs_peer": False})
    create_member_fixture(ixp, membership_properties={"speed": 10000, "is_rs_peer": True, "end_date": datetime(year=2024, month=4, day=1, tzinfo=timezone.utc)})

    generate_stats(MockLookup())

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1
    assert ixp_stats.capacity == 0.5
    assert ixp_stats.rs_peering_rate == 0


def test_does_not_count_member_twice_if_they_rejoin():
    ixp = IXPFactory()
    member = create_member_fixture(ixp, membership_properties={"end_date": datetime(year=2024, month=4, day=1, tzinfo=timezone.utc)})
    IXPMembershipRecordFactory(member=member)

    generate_stats(MockLookup())

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1


def test_does_not_count_members_not_yet_created():
    stats_date = datetime(year=2024, month=2, day=1, tzinfo=timezone.utc)
    ixp = IXPFactory(created=stats_date)
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2024, month=1, day=1)})
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2024, month=4, day=1)})

    generate_stats(MockLookup(), stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1


def test_does_not_count_ixps_not_yet_created():
    stats_date = datetime(year=2024, month=2, day=1, tzinfo=timezone.utc)
    ixp = IXPFactory(created=(stats_date + timedelta(days=60)))
    create_member_fixture(ixp, quantity=2)

    generate_stats(MockLookup(), stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats is None


def test_saves_local_asns_members_rate():
    ixp_one = IXPFactory()
    local_member_one = create_member_fixture(ixp_one)
    create_member_fixture(ixp_one, quantity=2)

    local_asns = [local_member_one.asn.number, ASNFactory().number, ASNFactory().number, ASNFactory().number]
    generate_stats(MockLookup(asns=local_asns))

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.local_asns_members_rate == 0.25


def test_saves_local_routed_asns_members_rate():
    ixp_one = IXPFactory()
    local_member_one = create_member_fixture(ixp_one)
    create_member_fixture(ixp_one, quantity=2)

    local_asns = [local_member_one.asn.number, ASNFactory().number, ASNFactory().number, ASNFactory().number]
    generate_stats(MockLookup(routed_asns=local_asns))

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.local_routed_asns_members_rate == 0.25


def test_calculate_local_asns_members_rate_returns_zero_if_no_asns_in_country():
    rate = calculate_local_asns_members_rate([12345], [])

    assert rate == 0


def test_calculate_local_asns_members_rate():
    rate = calculate_local_asns_members_rate([12345], [12345, 446, 789, 5050, 54321])

    assert rate == 0.2


def test_calculate_local_asns_members_rate_ignores_members_not_in_country_list():
    rate = calculate_local_asns_members_rate([12345, 789], [12345, 446, 5050, 54321])

    assert rate == 0.25


def test_counts_net_joins_and_net_leaves_since_12_months():
    stats_date = datetime(year=2024, month=2, day=1, tzinfo=timezone.utc)
    ixp = IXPFactory(created=stats_date)
    # One member joined more than 12 months ago and is still a member (i.e. not counted in either)
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2023, month=1, day=1)})
    # Two members joined within the last 12 months
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2024, month=1, day=1)})
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2023, month=12, day=1)})
    # One member joined more than 12 months ago but has since left
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2022, month=11, day=1), "end_date": datetime(year=2023, month=6, day=17)})
    # One member left and rejoined within the 12 months (so should not be counted)
    member = create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2022, month=11, day=1), "end_date": datetime(year=2023, month=6, day=17)})
    IXPMembershipRecordFactory(member=member, start_date=datetime(year=2023, month=11, day=1))

    generate_stats(MockLookup(), stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members_joined_last_12_months == 2
    assert ixp_stats.members_left_last_12_months == 1


def test_adds_member_growth_stats():
    stats_date = datetime(year=2025, month=3, day=1, tzinfo=timezone.utc)
    ixp = IXPFactory(created=stats_date)
    # Has 5 current members
    create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2023, month=1, day=1)}, quantity=5)
    last_month = (stats_date - timedelta(days=1)).replace(day=1).date()
    # Note the fixture would have had 5 members last month but we hardcode the stats to show only 4
    StatsPerIXPFactory(ixp=ixp, members=4, stats_date=last_month)

    generate_stats(MockLookup(), stats_date)

    new_ixp_stats = StatsPerIXP.objects.filter(stats_date=stats_date.date()).first()
    assert new_ixp_stats.monthly_members_change == 1
    assert new_ixp_stats.monthly_members_change_percent == 0.25


def test_saves_local_routed_asns_members_and_customers_rate():
    ixp_one = IXPFactory()
    local_member_one = create_member_fixture(ixp_one)
    create_member_fixture(ixp_one, quantity=2)
    customer_asn = ASNFactory().number

    local_asns = [local_member_one.asn.number, customer_asn, ASNFactory().number, ASNFactory().number]
    generate_stats(MockLookup(routed_asns=local_asns, customer_asns=[customer_asn]))

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.local_routed_asns_members_customers_rate == 0.5
