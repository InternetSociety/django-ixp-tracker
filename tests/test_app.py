from datetime import timezone
from uuid import UUID

import pytest
from faker.proxy import Faker

from ixp_tracker.event_store import DjangoEventStore, EventStore, Event, ValueNotChanged
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXPIdMapProjection,
    IXP_TRACKER_EVENT_MAP,
    IXP,
)
from ixp_tracker.models import IXPIdMap, StoredEvent
from tests.fixtures import StoredEventFactory

pytestmark = pytest.mark.django_db


class MemoryEventStore(EventStore):
    aggregate: IXP
    events: list = []

    def set_ixp(self, ixp: IXP):
        self.aggregate = ixp

    def store(self, event: Event) -> StoredEvent:
        self.events.append(event)
        return StoredEventFactory()

    def get_aggregate(self, aggregate_id: UUID, aggregate_type: type[IXP]) -> IXP:
        return self.aggregate


def test_registers_ixp(faker: Faker):
    app = IXPTracker(DjangoEventStore(IXP_TRACKER_EVENT_MAP), IXPIdMapProjection())

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
    es = DjangoEventStore(IXP_TRACKER_EVENT_MAP)
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


def test_updates_main_ixp_details(faker):
    es = DjangoEventStore(IXP_TRACKER_EVENT_MAP)
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

    new_name = name + "X"
    new_long_name = long_name + "X"
    new_city = faker.city()
    new_website = faker.url(schemes=["https"])
    new_country = faker.country_code()
    app.update_ixp(
        ixp.id,
        new_name,
        new_long_name,
        new_city,
        new_website,
        new_country,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.random_number(digits=3),
    )

    ixp = app.find_by_peeringdb_id(peeringdb_id)

    assert ixp.name == new_name
    assert ixp.long_name == new_long_name
    assert ixp.city == new_city
    assert ixp.website == new_website
    assert ixp.country_code == new_country


def test_does_not_update_fields_if_not_changed(faker):
    es = MemoryEventStore(IXP_TRACKER_EVENT_MAP)
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
    es.set_ixp(ixp)

    app.update_ixp(
        ixp.id,
        ixp.name,
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        ixp.org_id,
    )

    event = es.events.pop()

    assert isinstance(event.name, ValueNotChanged)
    assert isinstance(event.long_name, ValueNotChanged)
    assert isinstance(event.city, ValueNotChanged)
    assert isinstance(event.website, ValueNotChanged)
    assert isinstance(event.country_code, ValueNotChanged)
    assert isinstance(event.created, ValueNotChanged)
    assert isinstance(event.last_updated, ValueNotChanged)
    assert isinstance(event.org_id, ValueNotChanged)
