from dataclasses import asdict
from datetime import timezone, datetime

import pytest
from faker import Faker

from ixp_tracker.event_store import EventStore
from ixp_tracker.models import UpdatedIXPs
from tests.fixtures import (
    StoredEventFactory,
    create_ixp_event,
    build_app,
    create_asn,
    create_member,
    MemoryEventStore,
    create_ixp,
)

from ixp_tracker.ixp_tracker_aggregates import (
    IXP,
    IXPBecameActive,
    ASN,
    IXP_TRACKER_EVENT_MAP,
)
from ixp_tracker.ixp_tracker_projections import (
    IXPsLastUpdatedProjection,
    IXPIdMapProjection,
    ASNLookup,
)

pytestmark = pytest.mark.django_db


def test_handles_does_nothing_directly(faker: Faker):
    app, es = build_app()
    projection = IXPsLastUpdatedProjection(app)
    created_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    ixp = create_ixp(faker, es, created_date=created_date)
    events = es.db.get_events()
    event = events[0]

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0

    # handle() just gathers a list of IXPs to update so we expect no result from this
    projection.handle(event, ixp)

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0


def test_handles_ixp_created(faker: Faker):
    app, es = build_app()
    projection = IXPsLastUpdatedProjection(app)
    created_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    ixp = create_ixp(faker, es, created_date=created_date)
    events = es.db.get_events()
    event = events[0]

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0

    projection.handle(event, ixp)
    projection.finalise()

    saved = UpdatedIXPs.objects.get(aggregate_id=event.aggregate_id)
    assert saved.data["name"] == ixp.name
    assert saved.last_updated == event.event_date.date()


def test_handles_other_events(faker: Faker):
    app, es = build_app()
    projection = IXPsLastUpdatedProjection(app)
    created_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    ixp = create_ixp(faker, es, created_date=created_date)
    events = es.db.get_events()
    created_event = events[0]
    projection.handle(created_event, ixp)
    projection.finalise()

    current = UpdatedIXPs.objects.filter(aggregate_id=ixp.id).first()
    assert current is not None
    assert current.data["active"] is False

    # We create this as a separate event rather than using the fixture so we can show the stored state changes
    update_event = IXPBecameActive(True)
    became_active_event = StoredEventFactory(
        event_type="IXPBecameActive", aggregate_type="IXP", data={"active_status": True}
    )
    ixp.became_active(update_event)

    projection.handle(became_active_event, ixp)
    projection.finalise()

    saved = UpdatedIXPs.objects.get(aggregate_id=ixp.id)
    assert saved.data["name"] == ixp.name
    assert saved.last_updated == became_active_event.event_date.date()
    assert saved.data["active"]


class TestApp(ASNLookup):
    def __init__(self, asn):
        self.asn = asn

    def get_asn(self, as_number, as_at: datetime | None = None) -> ASN | None:
        return self.asn


def test_decorates_with_asn_data(faker: Faker):
    _, es = build_app()
    asn = create_asn(faker, es)
    projection = IXPsLastUpdatedProjection(TestApp(asn))
    created_date = faker.date_time_between(
        start_date="-3d", end_date="-2d", tzinfo=timezone.utc
    )
    ixp = create_ixp(faker, es, created_date=created_date)
    ixp = create_member(faker, es, ixp, asn, {"start_date": created_date})

    events = es.db.get_events()
    created_event = next(e for e in events if e.event_type == "IXPCreated")
    projection.handle(created_event, ixp)
    projection.finalise()

    saved = UpdatedIXPs.objects.get(aggregate_id=ixp.id)
    assert saved.data["name"] == ixp.name
    members = saved.data["members"]
    assert len(members) == 1
    member = members.pop()
    assert member["asn"]["asn"] == asn.number
    assert member["asn"]["network_type"] == asn.network_type.value
    assert member["asn"]["registration_country"] == asn.country_code
    assert member["asn"]["peering_policy"] == asn.peering_policy.value


def test_only_saves_active_members(faker: Faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es)
    projection = IXPsLastUpdatedProjection(TestApp(asn))
    created_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    ixp_created_event = create_ixp_event(faker, created_date=created_date)
    event = StoredEventFactory(
        event_type="IXPCreated",
        aggregate_type="IXP",
        data=(asdict(ixp_created_event)),
    )
    ixp = IXP(event.aggregate_id)
    ixp.created(ixp_created_event)
    id_map = IXPIdMapProjection()
    id_map.handle(event, ixp)
    ixp = create_member(
        faker, es, ixp, asn, {"start_date": created_date, "end_date": created_date}
    )

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0

    projection.handle(event, ixp)
    projection.finalise()

    saved = UpdatedIXPs.objects.get(aggregate_id=event.aggregate_id)
    members = saved.data["members"]
    assert len(members) == 0
