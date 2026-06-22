from datetime import datetime, timedelta, timezone

import pytest
from factory import Faker

from ixp_tracker.ixp_tracker_projections import ASNList, IXPIdMapProjection

from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP

from ixp_tracker.ixp_tracker import IXPTracker

from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore

from ixp_tracker.models import StatsPerCountryES
from ixp_tracker.stats import do_generate_stats
from tests.fixtures import (
    ASNFactory,
    MockLookup,
    MemoryEventStore,
    create_ixp,
    create_asn,
    create_member,
    StatsPerCountryESFactory,
)

pytestmark = pytest.mark.django_db
# Ensure default created date is before 1st of current month so it's counted in the stats
created_date = datetime.now(timezone.utc).replace(day=1) - timedelta(days=7)


def test_with_no_data_generates_no_stats():
    app, es = build_app(MemoryEventStore())
    do_generate_stats(MockLookup(), es_app=app)

    stats = StatsPerCountryES.objects.all()
    assert len(stats) == 249
    first_stat = stats.first()
    assert first_stat.member_count == 0


def test_generates_stats(faker: Faker):
    app, es = build_app(MemoryEventStore())
    ixp_one = create_ixp(faker, es, created_date=created_date, active_status=True)
    create_member(
        faker, es, ixp_one, create_asn(faker, es), {"start_date": created_date}
    )
    asn_one_multiple_ixps = create_asn(faker, es)
    create_member(
        faker, es, ixp_one, asn_one_multiple_ixps, {"start_date": created_date}
    )
    asn_two_multiple_ixps = create_asn(faker, es)
    create_member(
        faker, es, ixp_one, asn_two_multiple_ixps, {"start_date": created_date}
    )

    ixp_two = create_ixp(
        faker,
        es,
        created_date=created_date,
        active_status=True,
        country_code=ixp_one.country_code,
    )
    create_member(
        faker, es, ixp_two, create_asn(faker, es), {"start_date": created_date}
    )
    create_member(
        faker, es, ixp_two, asn_one_multiple_ixps, {"start_date": created_date}
    )
    create_member(
        faker, es, ixp_two, asn_two_multiple_ixps, {"start_date": created_date}
    )
    customer_asn = create_asn(faker, es)

    routed_asns_in_country = [
        asn_one_multiple_ixps.number,
        customer_asn.number,
        ASNFactory().number,
        ASNFactory().number,
    ]
    do_generate_stats(
        MockLookup(
            routed_asns=routed_asns_in_country,
            customer_asns=[customer_asn.number],
        ),
        es_app=app,
    )

    stats = StatsPerCountryES.objects.filter(country_code=ixp_one.country_code).first()
    assert stats.ixp_count == 2
    assert stats.routed_asn_count == 4
    assert stats.member_count == 4
    assert stats.domestic_network_membership == 0.25
    assert stats.domestic_network_coverage == 0.5


def test_generates_ixp_counts(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime.now(timezone.utc)
    one_month_before = (stats_date - timedelta(days=1)).replace(day=1)
    one_month_after = (stats_date + timedelta(days=35)).replace(day=1)
    # active_status only stores the current status whereas the stats need to generate historically
    # so the stats use the historical member count rather than active_status
    # currently_active with three members
    active = create_ixp(faker, es, created_date=created_date, active_status=True)
    create_member(
        faker,
        es,
        active,
        create_asn(faker, es),
        {
            "start_date": one_month_before,
            "end_date": one_month_after,
        },
    )
    create_member(
        faker,
        es,
        active,
        create_asn(faker, es),
        {
            "start_date": one_month_before,
            "end_date": one_month_after,
        },
    )
    create_member(
        faker,
        es,
        active,
        create_asn(faker, es),
        {
            "start_date": one_month_before,
            "end_date": one_month_after,
        },
    )
    # member active in the past
    member_in_past = create_ixp(
        faker,
        es,
        created_date=created_date,
        active_status=True,
        country_code=active.country_code,
    )
    create_member(
        faker,
        es,
        member_in_past,
        create_asn(faker, es),
        {
            "start_date": one_month_before,
            "end_date": one_month_before,
        },
    )
    # member not yet active (as we are generating historical stats there could be members in the future)
    member_in_future = create_ixp(
        faker,
        es,
        created_date=created_date,
        active_status=True,
        country_code=active.country_code,
    )
    create_member(
        faker,
        es,
        member_in_future,
        create_asn(faker, es),
        {"start_date": one_month_after},
    )
    # currently_active but only two members
    not_enough_members = create_ixp(
        faker,
        es,
        created_date=created_date,
        active_status=True,
        country_code=active.country_code,
    )
    create_member(
        faker,
        es,
        not_enough_members,
        create_asn(faker, es),
        {
            "start_date": one_month_before,
            "end_date": one_month_after,
        },
    )
    do_generate_stats(MockLookup(), stats_date, es_app=app)

    stats = StatsPerCountryES.objects.filter(country_code=active.country_code).first()
    assert stats.ixp_count == 1
    assert stats.member_count == 3


def test_handles_invalid_country(faker: Faker):
    app, es = build_app(MemoryEventStore())
    create_ixp(
        faker, es, created_date=created_date, active_status=True, country_code="XK"
    )

    do_generate_stats(MockLookup(), es_app=app)

    country_stats = StatsPerCountryES.objects.filter(country_code="XK").first()
    assert country_stats is None


def test_updates_existing_stats_entry():
    app, es = build_app(MemoryEventStore())
    date_now = datetime.now(timezone.utc)
    # Ensure stats_date and last_generated are always in the past so we can verify the updated last_generated
    stats_date = (date_now.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_generated = stats_date + timedelta(days=1)
    existing = StatsPerCountryESFactory(
        stats_date=stats_date, last_generated=last_generated
    )

    do_generate_stats(MockLookup(), stats_date, es_app=app)

    all_stats_for_country = StatsPerCountryES.objects.filter(
        country_code=existing.country_code
    )
    assert all_stats_for_country.count() == 1
    country_stats = all_stats_for_country.first()
    assert country_stats.last_generated > existing.last_generated
    assert country_stats.ixp_count == 0
    assert country_stats.routed_asn_count == 0
    assert country_stats.member_count == 0


def build_app(
    es_db: EventStorePersistence | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(ASNList())
    es.add_listener(IXPIdMapProjection())
    app = IXPTracker(es, MockLookup())
    return app, es
