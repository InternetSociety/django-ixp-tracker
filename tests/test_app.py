import pytest

from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker import IXPTracker, ISOCIdProjection
from ixp_tracker.models import ISOCId

pytestmark = pytest.mark.django_db


def test_registers_ixp(faker):
    app = IXPTracker(EventStore(), ISOCIdProjection())

    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    peeringdb_id = faker.random_number(digits=3)
    ixp = app.register_ixp(name, long_name, city, peeringdb_id)

    assert ixp.name == name
    assert ixp.long_name == long_name
    assert ixp.peeringdb_id == peeringdb_id


def test_assigns_isoc_id_to_ixp(faker):
    es = EventStore()
    app = IXPTracker(es, ISOCIdProjection())

    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    peeringdb_id = faker.random_number(digits=3)
    ixp = app.register_ixp(name, long_name, city, peeringdb_id)

    isoc_id = ISOCId.objects.get(aggregate_id=ixp.id)
    assert isoc_id.id > 0
