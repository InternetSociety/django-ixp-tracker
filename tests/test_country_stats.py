from datetime import datetime, timedelta, timezone

import pytest

from ixp_tracker.models import StatsPerCountry
from ixp_tracker.stats import generate_stats
from tests.fixtures import ASNFactory, IXPFactory, MockLookup, StatsPerCountryFactory, create_member_fixture

pytestmark = pytest.mark.django_db


def test_with_no_data_generates_no_stats():
    generate_stats(MockLookup())

    stats = StatsPerCountry.objects.all()
    assert len(stats) == 249
    first_stat = stats.first()
    assert first_stat.member_count == 0


def test_generates_stats():
    ixp_one = IXPFactory()
    create_member_fixture(ixp_one)
    member_one_multiple_ixps = create_member_fixture(ixp_one)
    member_two_multiple_ixps = create_member_fixture(ixp_one)
    ixp_two = IXPFactory(country_code=ixp_one.country_code)
    create_member_fixture(ixp_two)
    create_member_fixture(ixp_two, asn=member_one_multiple_ixps.asn)
    create_member_fixture(ixp_two, asn=member_two_multiple_ixps.asn)
    non_member_asn = ASNFactory()
    customer_asn = ASNFactory()

    asns_in_country = [member_one_multiple_ixps.asn.number, member_two_multiple_ixps.asn.number, non_member_asn.number]
    routed_asns_in_country = [member_one_multiple_ixps.asn.number, non_member_asn.number, customer_asn, ASNFactory().number]
    generate_stats(MockLookup(asns=asns_in_country, routed_asns=routed_asns_in_country, customer_asns=[customer_asn]))

    stats = StatsPerCountry.objects.filter(country_code=ixp_one.country_code).first()
    assert stats.ixp_count == 2
    assert stats.asn_count == 3
    assert stats.routed_asn_count == 4
    assert stats.member_count == 4
    assert stats.asns_ixp_member_rate == pytest.approx(0.666, abs=0.001)
    assert stats.routed_asns_ixp_member_rate == 0.25
    assert stats.routed_asns_ixp_member_customers_rate == 0.5


def test_generates_ixp_counts():
    stats_date = datetime.now(timezone.utc)
    one_month_before = (stats_date - timedelta(days=1)).replace(day=1)
    one_month_after = (stats_date + timedelta(days=35)).replace(day=1)
    # active_status only stores the current status whereas the stats need to generate historically
    # so the stats use the historical member count rather than active_status
    # currently_active with three members
    active = IXPFactory(active_status=True)
    create_member_fixture(active, membership_properties={"start_date": one_month_before, "end_date": one_month_after}, quantity=3)
    # member active in the past
    member_in_past = IXPFactory(active_status=True, country_code=active.country_code)
    create_member_fixture(member_in_past, membership_properties={"start_date": one_month_before, "end_date": one_month_before})
    # member not yet active (as we are generating historical stats there could be members in the future)
    member_in_future = IXPFactory(active_status=True, country_code=active.country_code)
    create_member_fixture(member_in_future, membership_properties={"start_date": one_month_after})
    # currently_active but only two members
    not_enough_members = IXPFactory(active_status=True, country_code=active.country_code)
    create_member_fixture(not_enough_members, membership_properties={"start_date": one_month_before, "end_date": one_month_after}, quantity=2)

    generate_stats(MockLookup(), stats_date)

    stats = StatsPerCountry.objects.filter(country_code=active.country_code).first()
    assert stats.ixp_count == 1
    assert stats.member_count == 3


def test_handles_invalid_country():
    IXPFactory(country_code="XK")

    generate_stats(MockLookup())

    country_stats = StatsPerCountry.objects.filter(country_code="XK").first()
    assert country_stats is None


def test_updates_existing_stats_entry():
    date_now = datetime.now(timezone.utc)
    # Ensure stats_date and last_generated are always in the past so we can verify the updated last_generated
    stats_date = (date_now.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_generated = stats_date + timedelta(days=1)
    existing = StatsPerCountryFactory(stats_date=stats_date, last_generated=last_generated)

    generate_stats(MockLookup(), stats_date)

    all_stats_for_country = StatsPerCountry.objects.filter(country_code=existing.country_code)
    assert all_stats_for_country.count() == 1
    country_stats = all_stats_for_country.first()
    assert country_stats.last_generated > existing.last_generated
    assert country_stats.ixp_count == 0
    assert country_stats.asn_count == 0
    assert country_stats.member_count == 0
