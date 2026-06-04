from dataclasses import dataclass

import pytest

from uuid import uuid4

from ixp_tracker.event_store import (
    DjangoEventStore,
    EventHasNoUpdatedFields,
    AggregateNotFound,
    EventStore,
    DomainEvent,
    EventNotMapped,
)
from ixp_tracker.models import CannotChangeStoredEvent, StoredEvent
from tests.fixtures import (
    TestAggregate,
    CreatedTestAggregate,
    TestAggregateUpdated,
    TEST_EVENT_MAP,
)

pytestmark = pytest.mark.django_db


@dataclass
class UnmappedDomainEvent(DomainEvent):
    foo: str


def test_saves_event():
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    assert stored_event.id == 1


def test_saves_event_type():
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    assert stored_event.event_type == "CreatedTestAggregate"


def test_saves_aggregate_type():
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    assert stored_event.aggregate_type == "TestAggregate"


def test_saves_event_data():
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    assert stored_event.data == {"foo": "bar"}


def test_saves_aggregate_sequence():
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")
    _ = es.store(aggregate, event)
    event = TestAggregateUpdated(foo="baz")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    assert stored_event.event_sequence == 2


def test_saved_events_cannot_be_changed():
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    with pytest.raises(CannotChangeStoredEvent):
        stored_event.event_type = "FooBar"
        stored_event.save()


def test_hydrates_aggregate():
    es = EventStore(TEST_EVENT_MAP, DjangoEventStore())

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, event)
    event = TestAggregateUpdated(foo="baz")
    es.store(aggregate, event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo == "baz"


def test_sets_property_to_none():
    es = EventStore(TEST_EVENT_MAP, DjangoEventStore())

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, event)
    event = TestAggregateUpdated(foo=None)
    es.store(aggregate, event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo is None


def test_ignores_properties_not_set_in_event():
    es = EventStore(TEST_EVENT_MAP, DjangoEventStore())

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, event)
    event = TestAggregateUpdated(bar="baz")
    es.store(aggregate, event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo == "bar"


def test_rejects_event_with_no_changes():
    es = EventStore(TEST_EVENT_MAP, DjangoEventStore())

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, event)
    event = TestAggregateUpdated()
    with pytest.raises(EventHasNoUpdatedFields):
        es.store(aggregate, event)


def test_raises_if_aggregate_not_found():
    es = EventStore(TEST_EVENT_MAP, DjangoEventStore())
    aggregate_id = uuid4()

    with pytest.raises(AggregateNotFound):
        es.get_aggregate(aggregate_id, TestAggregate)


def test_raises_if_event_not_mapped():
    es = EventStore(TEST_EVENT_MAP, DjangoEventStore())
    aggregate = TestAggregate(id=uuid4())

    event = StoredEvent(
        aggregate_id=aggregate.id,
        aggregate_type="TestAggregate",
        event_type="UnmappedEvent",
        event_sequence=1,
        data={},
    )
    event.save()

    with pytest.raises(EventNotMapped):
        es.get_aggregate(aggregate.id, TestAggregate)
