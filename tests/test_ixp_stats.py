from datetime import datetime, timedelta, timezone

import pytest
from faker import Faker

from ixp_tracker.ixp_tracker_aggregates import (
    IXPMemberJoined,
    RsPeeringStatusChange,
    IXPMemberLeft,
)
from ixp_tracker.json import stringify_date
from ixp_tracker.models import StatsPerIXP
from ixp_tracker.stats import do_generate_stats
from tests.fixtures import (
    MemoryEventStore,
    MockLookup,
    PeeringASNFactory,
    StatsPerIXPFactory,
    build_app,
    create_asn,
    create_ixp,
    create_member,
)

pytestmark = pytest.mark.django_db
# Ensure default created date is before 1st of current month so it's counted in the stats
start_of_current_month = datetime.now(timezone.utc).replace(day=1)
created_date = start_of_current_month - timedelta(days=7)


def test_with_no_data_generates_no_stats():
    app, _ = build_app(MemoryEventStore())
    do_generate_stats(MockLookup(), app)

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 0


def test_generates_capacity_rs_peering_and_member_count(faker: Faker):
    app, es = build_app(MemoryEventStore())
    es.time_travel(start_of_current_month)
    ixp = create_ixp(faker, es, created_date=created_date)
    asn_one = create_asn(faker, es)
    create_member(
        faker,
        es,
        ixp,
        asn_one,
        {"port_speed": 500, "is_rs_peer": True, "start_date": created_date},
    )
    asn_two = create_asn(faker, es)
    create_member(
        faker,
        es,
        ixp,
        asn_two,
        {"port_speed": 10000, "is_rs_peer": False, "start_date": created_date},
    )

    do_generate_stats(MockLookup(), app)

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 1
    ixp_stats = stats.first()
    assert ixp_stats.members == 2
    assert ixp_stats.capacity == 10.5
    assert ixp_stats.rs_peering_rate == 0.5


def test_generates_stats_for_first_of_month(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime.now(timezone.utc).replace(day=10)
    es.time_travel(stats_date.replace(day=1))
    create_ixp(faker, es, created_date=created_date)

    do_generate_stats(MockLookup(), app, stats_date)

    stats = StatsPerIXP.objects.all()
    assert len(stats) == 1
    ixp_stats = stats.first()
    assert ixp_stats.stats_date == stats_date.replace(day=1).date()


def test_does_not_count_members_marked_as_left(faker: Faker):
    app, es = build_app(MemoryEventStore())
    es.time_travel(start_of_current_month)
    ixp = create_ixp(faker, es, created_date=created_date)
    asn_one = create_asn(faker, es)
    create_member(
        faker,
        es,
        ixp,
        asn_one,
        {"port_speed": 500, "is_rs_peer": True, "start_date": created_date},
    )
    asn_two = create_asn(faker, es)
    create_member(
        faker,
        es,
        ixp,
        asn_two,
        {
            "port_speed": 10000,
            "is_rs_peer": False,
            "start_date": datetime(year=2024, month=4, day=1, tzinfo=timezone.utc),
            "end_date": datetime(year=2024, month=4, day=1, tzinfo=timezone.utc),
        },
    )

    do_generate_stats(MockLookup(), app)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1
    assert ixp_stats.capacity == 0.5
    assert ixp_stats.rs_peering_rate == 1


def test_does_not_count_member_twice_if_they_rejoin(faker: Faker):
    app, es = build_app(MemoryEventStore())
    es.time_travel(start_of_current_month)
    ixp = create_ixp(faker, es, created_date=created_date)
    asn = create_asn(faker, es)
    date_left = datetime(year=2024, month=4, day=1, tzinfo=timezone.utc)
    create_member(faker, es, ixp, asn, {"end_date": date_left})
    # Member rejoins
    date_rejoined = date_left + timedelta(weeks=1)
    join_event = IXPMemberJoined(
        asn.number,
        stringify_date(date_rejoined),
        stringify_date(date_rejoined),
        stringify_date(date_rejoined),
        True,
        500,
    )
    ixp.member_joined(join_event)
    es.store(ixp, join_event)

    do_generate_stats(MockLookup(), app)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1


def test_does_not_count_members_not_yet_created(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime(year=2024, month=2, day=1, tzinfo=timezone.utc)
    es.time_travel(stats_date)
    ixp = create_ixp(faker, es, created_date=stats_date)
    asn = create_asn(faker, es)
    date_joined = stats_date + timedelta(weeks=1)
    create_member(faker, es, ixp, asn, {"start_date": stats_date})
    create_member(faker, es, ixp, asn, {"start_date": date_joined})

    do_generate_stats(MockLookup(), app, stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members == 1


def test_does_not_count_ixps_not_yet_created(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime(year=2024, month=2, day=1, tzinfo=timezone.utc)
    ixp_created_date = stats_date + timedelta(weeks=1)
    es.time_travel(created_date)
    ixp = create_ixp(faker, es, created_date=ixp_created_date)
    asn = create_asn(faker, es)
    create_member(faker, es, ixp, asn, {"start_date": ixp_created_date})

    do_generate_stats(MockLookup(), app, stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats is None


def test_saves_domestic_network_membership_rate(faker: Faker):
    app, es = build_app(MemoryEventStore())
    es.time_travel(start_of_current_month)
    ixp = create_ixp(faker, es, created_date=created_date)
    # IXP has 2 members, one "local" and one not
    local_asn = create_asn(faker, es)
    create_member(faker, es, ixp, local_asn, {"start_date": created_date})
    non_local_asn = create_asn(faker, es)
    create_member(faker, es, ixp, non_local_asn, {"start_date": created_date})

    # There are 4 "local" ASNs including our local IXP member
    local_asns = [
        local_asn.number,
        PeeringASNFactory()["asn"],
        PeeringASNFactory()["asn"],
        PeeringASNFactory()["asn"],
    ]
    do_generate_stats(MockLookup(routed_asns=local_asns), app)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.domestic_network_membership == 0.25


def test_counts_net_joins_and_net_leaves_since_12_months(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime(year=2024, month=2, day=1, tzinfo=timezone.utc)
    date_more_than_12_months_ago = datetime(
        year=2023, month=1, day=1, tzinfo=timezone.utc
    )
    es.time_travel(date_more_than_12_months_ago)
    ixp = create_ixp(faker, es, created_date=date_more_than_12_months_ago)
    # One member joined more than 12 months ago and is still a member (i.e. not counted in either)
    create_member(
        faker,
        es,
        ixp,
        create_asn(faker, es),
        {"start_date": date_more_than_12_months_ago},
    )
    # One member joined more than 12 months ago but has since left
    asn_left_within_12_month_period = create_asn(faker, es)
    create_member(
        faker,
        es,
        ixp,
        asn_left_within_12_month_period,
        {
            "start_date": date_more_than_12_months_ago,
        },
    )
    # One member left and rejoined within the 12 months (so should not be counted)
    asn_left_and_rejoined = create_asn(faker, es)
    create_member(
        faker,
        es,
        ixp,
        asn_left_and_rejoined,
        {
            "start_date": datetime(year=2022, month=11, day=1, tzinfo=timezone.utc),
        },
    )

    date_one_month_ago = datetime(year=2024, month=1, day=1, tzinfo=timezone.utc)
    es.time_travel(date_one_month_ago)
    # One member joined more than 12 months ago but has since left
    asn_left_within_12_month_period_left = IXPMemberLeft(
        asn_left_within_12_month_period.number, stringify_date(date_one_month_ago)
    )
    ixp.member_left(asn_left_within_12_month_period_left)
    es.store(ixp, asn_left_within_12_month_period_left)
    # One member left and rejoined within the 12 months (so should not be counted)
    asn_left_and_rejoined_left = IXPMemberLeft(
        asn_left_and_rejoined.number, stringify_date(date_one_month_ago)
    )
    ixp.member_left(asn_left_and_rejoined_left)
    es.store(ixp, asn_left_and_rejoined_left)
    date_rejoined = datetime(year=2023, month=11, day=11, tzinfo=timezone.utc)
    join_event = IXPMemberJoined(
        asn_left_and_rejoined.number,
        stringify_date(date_rejoined),
        stringify_date(date_rejoined),
        stringify_date(date_rejoined),
        True,
        500,
    )
    ixp.member_joined(join_event)
    es.store(ixp, join_event)
    # Two members joined within the last 12 months
    create_member(
        faker,
        es,
        ixp,
        create_asn(faker, es),
        {"start_date": date_one_month_ago},
    )
    create_member(
        faker,
        es,
        ixp,
        create_asn(faker, es),
        {"start_date": datetime(year=2023, month=12, day=1, tzinfo=timezone.utc)},
    )

    do_generate_stats(MockLookup(), app, stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.members_joined_last_12_months == 2
    assert ixp_stats.members_left_last_12_months == 1


def test_adds_member_growth_stats(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime(year=2025, month=3, day=1, tzinfo=timezone.utc)
    earlier_date = (stats_date - timedelta(days=1)).replace(day=1)
    es.time_travel(earlier_date)
    ixp = create_ixp(faker, es, created_date=earlier_date)
    # Has 5 current members
    # 4 joined in the past
    for _ in range(1, 5):
        create_member(
            faker,
            es,
            ixp,
            create_asn(faker, es),
            {"start_date": datetime(year=2023, month=1, day=1, tzinfo=timezone.utc)},
        )
    # One joined in the last month
    es.time_travel(stats_date)
    create_member(
        faker,
        es,
        ixp,
        create_asn(faker, es),
        {"start_date": datetime(year=2025, month=2, day=2, tzinfo=timezone.utc)},
    )

    do_generate_stats(MockLookup(), app, stats_date)

    new_ixp_stats = StatsPerIXP.objects.filter(stats_date=stats_date.date()).first()
    assert new_ixp_stats.monthly_members_change == 1
    assert new_ixp_stats.monthly_members_change_percent == 0.25


def test_saves_local_routed_asns_members_and_customers_rate(faker: Faker):
    app, es = build_app(MemoryEventStore())
    es.time_travel(start_of_current_month)
    ixp = create_ixp(faker, es, created_date=created_date)
    local_asn = create_asn(faker, es)
    create_member(faker, es, ixp, local_asn, {"start_date": created_date})
    create_member(faker, es, ixp, create_asn(faker, es), {"start_date": created_date})
    create_member(faker, es, ixp, create_asn(faker, es), {"start_date": created_date})
    customer_asn = PeeringASNFactory()["asn"]

    local_asns = [
        local_asn.number,
        customer_asn,
        PeeringASNFactory()["asn"],
        PeeringASNFactory()["asn"],
    ]
    do_generate_stats(
        MockLookup(routed_asns=local_asns, customer_asns=[customer_asn]), es_app=app
    )

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.domestic_network_coverage == 0.5


def test_updates_existing_stats(faker: Faker):
    app, es = build_app(MemoryEventStore())
    date_now = datetime.now(timezone.utc)
    # Ensure stats_date and last_generated are always in the past so we can verify the updated last_generated
    stats_date = (date_now.replace(day=1) - timedelta(days=1)).replace(day=1)
    es.time_travel(stats_date)
    last_generated = stats_date + timedelta(days=1)
    ixp = create_ixp(faker, es, created_date=stats_date)
    create_member(faker, es, ixp, create_asn(faker, es), {"start_date": stats_date})
    create_member(faker, es, ixp, create_asn(faker, es), {"start_date": stats_date})
    isoc_id = app.find_isoc_id(ixp.id)
    existing = StatsPerIXPFactory(
        stats_date=stats_date, ixp=isoc_id, members=1, last_generated=last_generated
    )

    do_generate_stats(MockLookup(), app, stats_date)

    all_stats_for_ixp = StatsPerIXP.objects.filter(ixp=isoc_id)
    assert all_stats_for_ixp.count() == 1
    ixp_stats = all_stats_for_ixp.first()
    assert ixp_stats.last_generated > existing.last_generated
    assert ixp_stats.members > existing.members


def test_saves_rs_peering_counts(faker: Faker):
    app, es = build_app(MemoryEventStore())
    stats_date = datetime(year=2025, month=3, day=1, tzinfo=timezone.utc)
    previous_month = (stats_date - timedelta(days=1)).replace(day=1)
    es.time_travel(previous_month)
    ixp = create_ixp(faker, es, created_date=previous_month)
    rs_peering_asn = create_asn(faker, es)
    rs_depeering_asn = create_asn(faker, es)
    # Pre-existing member peers with the RS
    create_member(
        faker,
        es,
        ixp,
        rs_depeering_asn,
        {
            "start_date": datetime(year=2023, month=1, day=1, tzinfo=timezone.utc),
            "is_rs_peer": True,
        },
    )
    # Four more pre-existing members peer with the RS
    for _ in range(1, 5):
        create_member(
            faker,
            es,
            ixp,
            create_asn(faker, es),
            {
                "start_date": datetime(year=2023, month=1, day=1, tzinfo=timezone.utc),
                "is_rs_peer": True,
            },
        )
    # One new route server peer in the last month
    es.time_travel(stats_date)
    create_member(
        faker,
        es,
        ixp,
        rs_peering_asn,
        {
            "start_date": datetime(year=2025, month=2, day=2, tzinfo=timezone.utc),
            "is_rs_peer": True,
        },
    )
    # One pre-existing RS peer depeers in the last month
    rspeeringstatuschange_event = RsPeeringStatusChange(
        rs_depeering_asn.number,
        False,
        stringify_date(datetime(year=2025, month=2, day=2, tzinfo=timezone.utc)),
    )
    ixp.rs_peering_status_change(rspeeringstatuschange_event)
    es.store(ixp, rspeeringstatuschange_event)

    do_generate_stats(MockLookup(), app, stats_date)

    ixp_stats = StatsPerIXP.objects.all().first()
    assert ixp_stats.monthly_rs_peered_members_count == 1
    assert ixp_stats.monthly_rs_depeered_members_count == 1
    assert ixp_stats.monthly_rs_peered_members == [rs_peering_asn.number]
    assert ixp_stats.monthly_rs_depeered_members == [rs_depeering_asn.number]
