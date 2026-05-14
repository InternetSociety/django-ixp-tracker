import pytest

from ixp_tracker.ixp_tracker import IXPIdMapProjection
from ixp_tracker.models import IXPIdMap
from tests.fixtures import StoredEventFactory, IXPIdMapFactory

pytestmark = pytest.mark.django_db


def test_creates_new_isoc_id():
    projection = IXPIdMapProjection()
    event = StoredEventFactory(event_type="IXPCreated", aggregate_type="IXP")

    current = IXPIdMap.objects.all()
    assert current.count() == 0

    projection.handle(event)

    saved = IXPIdMap.objects.get(aggregate_id=event.aggregate_id)
    assert saved.id > 0
    assert saved.peeringdb_id is None


def test_handles_duplicate_events():
    projection = IXPIdMapProjection()
    event = StoredEventFactory(event_type="IXPCreated", aggregate_type="IXP")

    # This shouldn't happen but if it does we just handle it silently
    # If this becomes a problem we could add event sequence tracking to projections
    projection.handle(event)
    projection.handle(event)

    saved = IXPIdMap.objects.all()
    assert saved.count() == 1


def test_saves_peeringdb_id(faker):
    projection = IXPIdMapProjection()
    peeringdb_id = faker.random_number(digits=3)
    event = StoredEventFactory(
        event_type="IXPCreated",
        aggregate_type="IXP",
        data={"peeringdb_id": peeringdb_id},
    )

    current = IXPIdMap.objects.all()
    assert current.count() == 0

    projection.handle(event)

    saved = IXPIdMap.objects.get(aggregate_id=event.aggregate_id)
    assert saved.peeringdb_id == peeringdb_id


def test_returns_none_if_peering_db_id_not_found(faker):
    projection = IXPIdMapProjection()
    peeringdb_id = faker.random_number(digits=3)

    current = IXPIdMap.objects.all()
    assert current.count() == 0

    id_map = projection.find_by_peeringdb_id(peeringdb_id)

    assert id_map is None


def test_returns_id_if_peeringdb_id_is_found(faker):
    projection = IXPIdMapProjection()
    peeringdb_id = faker.random_number(digits=3)
    IXPIdMapFactory(peeringdb_id=peeringdb_id)

    id_map = projection.find_by_peeringdb_id(peeringdb_id)

    assert id_map.aggregate_id is not None
