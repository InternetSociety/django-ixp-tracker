from dataclasses import asdict
from datetime import timezone

import pytest
from faker import Faker

from ixp_tracker.models import UpdatedIXPs
from tests.fixtures import StoredEventFactory, create_ixp_event, build_app

from ixp_tracker.ixp_tracker_aggregates import IXP, IXPBecameActive
from ixp_tracker.ixp_tracker_projections import (
    IXPsLastUpdatedProjection,
    IXPIdMapProjection,
)

pytestmark = pytest.mark.django_db


def test_handles_does_nothing_directly(faker: Faker):
    app, _ = build_app()
    projection = IXPsLastUpdatedProjection(app)
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

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0

    # handle(0 just gathers a list of IXPs to update so we expect no result from this
    projection.handle(event, ixp)

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0


def test_handles_ixp_created(faker: Faker):
    app, _ = build_app()
    projection = IXPsLastUpdatedProjection(app)
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

    current = UpdatedIXPs.objects.all()
    assert current.count() == 0

    projection.handle(event, ixp)
    projection.finalise()

    saved = UpdatedIXPs.objects.get(aggregate_id=event.aggregate_id)
    assert saved.data["name"] == ixp.name
    assert saved.last_updated == event.event_date.date()


def test_handles_other_events(faker: Faker):
    app, _ = build_app()
    projection = IXPsLastUpdatedProjection(app)
    ixp_created_event = create_ixp_event(faker)
    original_event_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    event = StoredEventFactory(
        event_type="IXPCreated",
        aggregate_type="IXP",
        data=(asdict(ixp_created_event)),
        event_date=original_event_date,
    )
    ixp = IXP(event.aggregate_id)
    ixp.created(ixp_created_event)
    id_map = IXPIdMapProjection()
    id_map.handle(event, ixp)
    projection.handle(event, ixp)
    projection.finalise()

    current = UpdatedIXPs.objects.filter(aggregate_id=ixp.id).first()
    assert current is not None
    assert current.data["active_status"] is False

    update_event = IXPBecameActive(True)
    stored_event = StoredEventFactory(
        event_type="IXPBecameActive", aggregate_type="IXP", data={"active_status": True}
    )
    ixp.became_active(update_event)

    projection.handle(stored_event, ixp)
    projection.finalise()

    saved = UpdatedIXPs.objects.get(aggregate_id=event.aggregate_id)
    assert saved.data["name"] == ixp.name
    assert saved.last_updated == stored_event.event_date.date()
    assert saved.data["active_status"]
