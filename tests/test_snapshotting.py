from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from ixp_tracker.event_store import EventStore, Aggregate, DomainEvent
from ixp_tracker.ixp_tracker import DATE_FORMAT
from tests.fixtures import (
    TestAggregate,
    TEST_EVENT_MAP,
    MemoryEventStore,
    CreatedTestAggregate,
    TestAggregateUpdated,
)


def test_saves_snapshot():
    es = EventStore(TEST_EVENT_MAP, MemoryEventStore())

    aggregate = TestAggregate(id=uuid4())
    aggregate.created(CreatedTestAggregate(foo="bar"))
    es.save_snapshot(aggregate)

    snapshot = es.load_snapshot(aggregate.id, TestAggregate)
    assert snapshot.foo == "bar"


def test_respects_time_travel_when_saving_snapshot(faker):
    mes = MemoryEventStore()
    es = EventStore(TEST_EVENT_MAP, mes)
    time_in_past = faker.date_time_between(
        start_date="-1w", end_date="-1d", tzinfo=timezone.utc
    )
    es.time_travel(time_in_past)

    aggregate = TestAggregate(id=uuid4())
    aggregate.created(CreatedTestAggregate(foo="bar"))
    es.save_snapshot(aggregate)

    snapshot = mes.snapshots[aggregate.id]
    assert snapshot[2] == time_in_past


def test_saves_datetime_to_snapshot():
    @dataclass
    class AddedDatetime(DomainEvent):
        foo: datetime

    class DatetimeAggregate(Aggregate):
        foo: datetime

        def created(self, event: AddedDatetime):
            self.foo = event.foo

        def snapshot(self):
            values = super().snapshot()
            values["foo"] = self.foo.strftime(DATE_FORMAT)
            return values

        def hydrate(self, data: dict):
            super().hydrate(data)
            self.foo = datetime.strptime(data["foo"], DATE_FORMAT)

    es = EventStore(TEST_EVENT_MAP, MemoryEventStore())

    aggregate = DatetimeAggregate(id=uuid4())
    now = datetime.now(timezone.utc)
    aggregate.created(AddedDatetime(foo=now))
    es.save_snapshot(aggregate)

    snapshot = es.load_snapshot(aggregate.id, DatetimeAggregate)
    assert snapshot.foo == now.replace(microsecond=0)


def test_rehydrate_from_snapshot():
    mes = MemoryEventStore()
    es = EventStore(TEST_EVENT_MAP, mes)

    aggregate = TestAggregate(id=uuid4())
    created_event = CreatedTestAggregate(foo="bar")
    es.store(aggregate, created_event)
    aggregate.created(created_event)
    es.save_snapshot(aggregate)
    updated_event = TestAggregateUpdated(foo="baz")
    es.store(aggregate, updated_event)
    aggregate.updated(updated_event)

    snapshot = es.get_aggregate(aggregate.id, TestAggregate)
    assert snapshot.foo == "baz"
    # Lets also check that this aggregate was actually hydrated from a snapshot
    assert aggregate.id in mes.snapshots_read
