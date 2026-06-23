from datetime import timedelta, timezone
from statistics import median

import pytest
from faker import Faker
from ixp_tracker.ixp_tracker_projections import (
    ASNList,
    IXPIdMapProjection,
    IXPsLastUpdatedProjection,
)

from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP

from ixp_tracker.ixp_tracker import IXPTracker

from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore

from tests.fixtures import (
    create_ixp,
    TestLookup,
    create_member,
    create_asn,
)

pytestmark = pytest.mark.django_db

test_cut_off = Faker().date_time_between(
    start_date="-4w", end_date="-1w", tzinfo=timezone.utc
)
before_cut_off_date = test_cut_off - timedelta(days=1)
after_cut_off_date = test_cut_off + timedelta(days=1)
test_cut_off_date = test_cut_off.date()


def test_with_no_ixps_returns_nothing():
    app, es = build_app()
    records = app.fetch_updated_ixp_records(test_cut_off_date)

    assert len(records) == 0


def test_does_not_return_ixp_updated_before_cut_off(faker: Faker):
    app, es = build_app()
    es.time_travel(before_cut_off_date)
    create_ixp(faker, es, created_date=before_cut_off_date)

    records = app.fetch_updated_ixp_records(test_cut_off_date)

    assert len(records) == 0


def test_returns_ixp_updated_after_cut_off(faker: Faker):
    app, es = build_app()
    ixp = create_ixp(faker, es, created_date=after_cut_off_date)
    create_member(faker, es, ixp, create_asn(faker, es))

    records = app.fetch_updated_ixp_records(test_cut_off_date)

    assert len(records) == 1
    ixp_record = records[0]
    assert len(ixp_record["members"]) == 1


def test_returns_ixp_updated_on_cut_off(faker: Faker):
    app, es = build_app()
    es.time_travel(test_cut_off)
    ixp = create_ixp(faker, es, created_date=test_cut_off)
    create_member(faker, es, ixp, create_asn(faker, es))

    records = app.fetch_updated_ixp_records(test_cut_off_date)

    assert len(records) == 1
    ixp_record = records[0]
    assert len(ixp_record["members"]) == 1


def test_returns_ixp_with_member_marked_ended_after_cut_off(faker: Faker):
    app, es = build_app()
    ixp = create_ixp(faker, es, created_date=before_cut_off_date)
    create_member(
        faker,
        es,
        ixp,
        create_asn(faker, es),
        {"start_date": before_cut_off_date, "end_date": after_cut_off_date},
    )

    records = app.fetch_updated_ixp_records(test_cut_off_date)

    assert len(records) == 1
    # The IXP is listed because a member has been updated since the cut off, but that member is marked left so isn't listed
    ixp_record = records[0]
    assert len(ixp_record["members"]) == 0


def test_with_no_updated_date_returns_count_ixps(faker: Faker):
    app, es = build_app()
    peeringdb_ids = [faker.unique.random_int(min=1) for _ in range(3)]
    create_ixp(
        faker, es, peeringdb_id=peeringdb_ids.pop(), created_date=before_cut_off_date
    )
    create_ixp(
        faker, es, peeringdb_id=peeringdb_ids.pop(), created_date=before_cut_off_date
    )
    create_ixp(
        faker, es, peeringdb_id=peeringdb_ids.pop(), created_date=before_cut_off_date
    )

    records = app.fetch_updated_ixp_records(None, 2)

    assert len(records) == 2


def test_with_offset_returns_records_with_that_id_or_greater(faker: Faker):
    app, es = build_app()
    peeringdb_ids = [faker.unique.random_int(min=1) for _ in range(3)]
    isoc_ids = []
    for _ in range(3):
        ixp = create_ixp(
            faker,
            es,
            peeringdb_id=peeringdb_ids.pop(),
            created_date=before_cut_off_date,
        )
        isoc_ids.append(app.find_isoc_id(ixp.id) or 0)
    last_id = max(isoc_ids)

    records = app.fetch_updated_ixp_records(None, first_id=last_id)

    assert len(records) == 1
    assert records[0]["id"] == last_id


def test_with_count_and_offset_returns_requested_slice_of_records(faker: Faker):
    app, es = build_app()
    peeringdb_ids = [faker.unique.random_int(min=1) for _ in range(3)]
    isoc_ids = []
    for _ in range(3):
        ixp = create_ixp(
            faker,
            es,
            peeringdb_id=peeringdb_ids.pop(),
            created_date=before_cut_off_date,
        )
        isoc_ids.append(app.find_isoc_id(ixp.id) or 0)
    middle_id = int(median(isoc_ids))

    records = app.fetch_updated_ixp_records(None, 1, middle_id)

    assert len(records) == 1
    assert records[0]["id"] == middle_id


def test_with_offset_after_last_id_returns_nothing(faker: Faker):
    app, es = build_app()
    peeringdb_ids = [faker.unique.random_int(min=1) for _ in range(3)]
    isoc_ids = []
    for _ in range(3):
        ixp = create_ixp(
            faker,
            es,
            peeringdb_id=peeringdb_ids.pop(),
            created_date=before_cut_off_date,
        )
        isoc_ids.append(app.find_isoc_id(ixp.id) or 0)
    last_id = max(isoc_ids)

    records = app.fetch_updated_ixp_records(None, first_id=(last_id + 1))

    assert len(records) == 0


def build_app(
    es_db: EventStorePersistence | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    es.add_listener(IXPsLastUpdatedProjection())
    app = IXPTracker(es, TestLookup())
    return app, es
