from datetime import timezone

import pytest
from faker.proxy import Faker

from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXPIdMapProjection,
    IXP_TRACKER_EVENT_MAP,
)
from ixp_tracker.models import IXPIdMap

pytestmark = pytest.mark.django_db


def test_registers_ixp(faker: Faker):
    app = IXPTracker(EventStore(IXP_TRACKER_EVENT_MAP), IXPIdMapProjection())

    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    peeringdb_id = faker.random_number(digits=3)
    ixp = app.register_ixp(
        name,
        long_name,
        city,
        peeringdb_id,
        faker.url(schemes=["https"]),
        faker.country_code(),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        False,
        False,
        faker.random_number(digits=3),
        faker.random_number(digits=2),
    )

    assert ixp.name == name
    assert ixp.long_name == long_name
    assert ixp.peeringdb_id == peeringdb_id


def test_assigns_isoc_id_to_ixp(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP)
    app = IXPTracker(es, IXPIdMapProjection())

    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    peeringdb_id = faker.random_number(digits=3)
    ixp = app.register_ixp(
        name,
        long_name,
        city,
        peeringdb_id,
        faker.url(schemes=["https"]),
        faker.country_code(),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        False,
        False,
        faker.random_number(digits=3),
        faker.random_number(digits=2),
    )

    isoc_id = IXPIdMap.objects.get(aggregate_id=ixp.id)
    assert isoc_id.id > 0
