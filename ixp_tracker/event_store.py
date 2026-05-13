import re
from abc import ABC
from dataclasses import dataclass, asdict
from typing import TypeVar
from uuid import UUID

from ixp_tracker.models import StoredEvent

convert_event_type_to_method_name = re.compile(r"(?<!^)(?=[A-Z])")
T = TypeVar("T")


@dataclass()
class Aggregate(ABC):
    id: UUID


@dataclass
class Event(ABC):
    aggregate: Aggregate


class ValueNotChanged:
    pass


class EventHasNoUpdatedFields(Exception):
    pass


class AggregateNotFound(Exception):
    pass


class Projection(ABC):
    def handle(self, event: StoredEvent):
        pass


class EventStore:
    listeners: list[Projection]

    def __init__(self):
        self.listeners = []

    def store(self, event: Event) -> StoredEvent:
        previous_event = (
            StoredEvent.objects.filter(aggregate_id=event.aggregate.id)
            .order_by("-event_sequence")
            .first()
        )
        event_sequence = 1
        if previous_event:
            event_sequence = previous_event.event_sequence + 1
        event_data = asdict(event)
        event_data = {
            key: value
            for key, value in event_data.items()
            if key not in ["aggregate"] and not isinstance(value, ValueNotChanged)
        }
        if len(event_data.keys()) == 0:
            raise EventHasNoUpdatedFields

        stored_event = StoredEvent(
            aggregate_id=event.aggregate.id,
            aggregate_type=type(event.aggregate).__name__,
            event_type=type(event).__name__,
            event_sequence=event_sequence,
            data=event_data,
        )
        stored_event.save()
        for listener in self.listeners:
            listener.handle(stored_event)

        return stored_event

    def get_aggregate(self, aggregate_id: UUID, aggregate_type: T) -> T:
        events = (
            StoredEvent.objects.filter(aggregate_id=aggregate_id)
            .order_by("event_sequence")
            .all()
        )
        if events.count() == 0:
            raise AggregateNotFound

        aggregate = None
        for event in events:
            if aggregate is None:
                aggregate = aggregate_type(aggregate_id)
            method_name = event.event_type.replace(aggregate_type.__name__, "")
            method_name = convert_event_type_to_method_name.sub(
                "_", method_name
            ).lower()
            getattr(aggregate, method_name)(**event.data)
        return aggregate

    def add_listener(self, projection: Projection):
        self.listeners.append(projection)
