from dataclasses import dataclass
from datetime import timezone, datetime, timedelta

import pytest

from uuid import uuid4

from faker import Faker

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
        event_date=datetime.now(timezone.utc),
        event_sequence=1,
        data={},
    )
    event.save()

    with pytest.raises(EventNotMapped):
        es.get_aggregate(aggregate.id, TestAggregate)


def test_time_machine_saves_event_in_the_past(faker):
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)
    time_in_past = faker.date_time_between(
        start_date="-1w", end_date="-1d", tzinfo=timezone.utc
    )
    es.time_travel(time_in_past)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(foo="bar")

    es.store(aggregate, event)

    stored_event = des.get_events().pop()
    assert stored_event.event_date == time_in_past


def test_retrieves_past_state_of_aggregate_using_time(faker: Faker):
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)
    time_in_past = faker.date_time_between(
        start_date="-2w", end_date="-1w", tzinfo=timezone.utc
    )

    # Create an aggregate in the past using time travel
    es.time_travel(time_in_past)
    aggregate = TestAggregate(id=uuid4())
    create_event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, create_event)

    # Update the aggregate in real time
    es.time_travel(None)
    update_event = TestAggregateUpdated(foo="baz")
    es.store(aggregate, update_event)

    time_before_update = datetime.now(timezone.utc) - timedelta(days=1)
    aggregate_in_past = es.get_aggregate(
        aggregate.id, TestAggregate, time_before_update
    )

    assert aggregate_in_past.foo == "bar"


def test_retrieves_past_state_of_aggregate_using_sequence(faker: Faker):
    des = DjangoEventStore()
    es = EventStore(TEST_EVENT_MAP, des)
    time_in_past = faker.date_time_between(
        start_date="-2w", end_date="-1w", tzinfo=timezone.utc
    )

    # Create an aggregate in the past using time travel
    es.time_travel(time_in_past)
    aggregate = TestAggregate(id=uuid4())
    create_event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, create_event)

    # Update the aggregate in real time
    es.time_travel(None)
    update_event = TestAggregateUpdated(foo="baz")
    es.store(aggregate, update_event)

    # We should retrieve the aggregate after the event with the supplied sequence has been applied
    aggregate_in_past = es.get_aggregate(aggregate.id, TestAggregate, version=1)

    assert aggregate_in_past.foo == "bar"
