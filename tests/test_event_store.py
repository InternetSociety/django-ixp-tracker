from typing import Optional

import pytest

from dataclasses import dataclass
from uuid import uuid4

from ixp_tracker.event_store import (
    EventStore,
    Event,
    Aggregate,
    ValueNotChanged,
    EventHasNoUpdatedFields,
    AggregateNotFound,
)
from ixp_tracker.models import CannotChangeStoredEvent

pytestmark = pytest.mark.django_db


@dataclass
class CreatedTestAggregate(Event):
    foo: str


@dataclass
class TestAggregateUpdated(Event):
    foo: Optional[str] = ValueNotChanged()
    bar: str = ValueNotChanged()


class TestAggregate(Aggregate):
    foo: str
    bar: Optional[str] = None

    def created(self, foo: str):
        self.foo = foo

    def updated(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_saves_event():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.id == 1


def test_saves_event_type():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.event_type == "CreatedTestAggregate"


def test_saves_aggregate_type():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.aggregate_type == "TestAggregate"


def test_saves_event_data():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.data == {"foo": "bar"}


def test_saves_aggregate_sequence():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    _ = es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, foo="baz")

    stored_event = es.store(event)

    assert stored_event.event_sequence == 2


def test_saved_events_cannot_be_changed():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    with pytest.raises(CannotChangeStoredEvent):
        stored_event.event_type = "FooBar"
        stored_event.save()


def test_hydrates_aggregate():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, foo="baz")
    es.store(event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo == "baz"


def test_sets_property_to_none():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, foo=None)
    es.store(event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo is None


def test_ignores_properties_not_set_in_event():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, bar="baz")
    es.store(event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo == "bar"


def test_rejects_event_with_no_changes():
    es = EventStore()

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate)
    with pytest.raises(EventHasNoUpdatedFields):
        es.store(event)


def test_raises_if_aggregate_not_found():
    es = EventStore()
    aggregate_id = uuid4()

    with pytest.raises(AggregateNotFound):
        es.get_aggregate(aggregate_id, TestAggregate)
