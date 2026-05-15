import pytest

from uuid import uuid4

from ixp_tracker.event_store import (
    DjangoEventStore,
    EventHasNoUpdatedFields,
    AggregateNotFound,
)
from ixp_tracker.models import CannotChangeStoredEvent
from tests.fixtures import (
    TestAggregate,
    CreatedTestAggregate,
    TestAggregateUpdated,
    TEST_EVENT_MAP,
)

pytestmark = pytest.mark.django_db


def test_saves_event():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.id == 1


def test_saves_event_type():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.event_type == "CreatedTestAggregate"


def test_saves_aggregate_type():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.aggregate_type == "TestAggregate"


def test_saves_event_data():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    assert stored_event.data == {"foo": "bar"}


def test_saves_aggregate_sequence():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    _ = es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, foo="baz")

    stored_event = es.store(event)

    assert stored_event.event_sequence == 2


def test_saved_events_cannot_be_changed():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")

    stored_event = es.store(event)

    with pytest.raises(CannotChangeStoredEvent):
        stored_event.event_type = "FooBar"
        stored_event.save()


def test_hydrates_aggregate():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, foo="baz")
    es.store(event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo == "baz"


def test_sets_property_to_none():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, foo=None)
    es.store(event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo is None


def test_ignores_properties_not_set_in_event():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate, bar="baz")
    es.store(event)

    saved_aggregate = es.get_aggregate(aggregate.id, TestAggregate)

    assert saved_aggregate.foo == "bar"


def test_rejects_event_with_no_changes():
    es = DjangoEventStore(TEST_EVENT_MAP)

    aggregate = TestAggregate(id=uuid4())
    event = CreatedTestAggregate(aggregate=aggregate, foo="bar")
    es.store(event)
    event = TestAggregateUpdated(aggregate=aggregate)
    with pytest.raises(EventHasNoUpdatedFields):
        es.store(event)


def test_raises_if_aggregate_not_found():
    es = DjangoEventStore(TEST_EVENT_MAP)
    aggregate_id = uuid4()

    with pytest.raises(AggregateNotFound):
        es.get_aggregate(aggregate_id, TestAggregate)
