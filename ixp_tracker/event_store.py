import logging
import re
from abc import ABC
from dataclasses import dataclass, asdict
from typing import TypeVar
from uuid import UUID

# At some point we might want to change the ES persistence to depend on a neutral DTO rather than this Django model
from ixp_tracker.models import StoredEvent

logger = logging.getLogger("ixp_tracker")

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
    def __init__(self):
        if self.__getattribute__("aggregate_types") is None:
            self.aggregate_types = []
        if self.__getattribute__("events") is None:
            self.events = []

    def handle(self, event: StoredEvent):
        if event.aggregate_type not in self.aggregate_types:
            return
        if event.event_type not in self.events:
            return
        self.do_handle(event)

    def do_handle(self, event: StoredEvent):
        pass


class EventStorePersistence(ABC):
    def get_event_sequence(self, event: Event) -> int:
        pass

    def save_event(self, event: StoredEvent):
        pass

    def get_aggregate_events(
        self, aggregate_id: UUID, aggregate_type: type[T]
    ) -> list[StoredEvent]:
        pass


class EventStore:
    listeners: list[Projection]
    event_map: dict[str, type[Event]]
    db: EventStorePersistence

    def __init__(self, event_map, db: EventStorePersistence):
        self.listeners = []
        self.event_map = event_map
        self.db = db

    def store(self, event: Event) -> StoredEvent:
        event_sequence = self.db.get_event_sequence(event)
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
        self.db.save_event(stored_event)
        for listener in self.listeners:
            listener.handle(stored_event)

        return stored_event

    def get_aggregate(self, aggregate_id: UUID, aggregate_type: type[T]) -> T:
        events = self.db.get_aggregate_events(aggregate_id, aggregate_type)
        if len(events) == 0:
            raise AggregateNotFound

        aggregate = None
        for event in events:
            if aggregate is None:
                aggregate = aggregate_type(aggregate_id)
            method_name = event.event_type.replace(aggregate_type.__name__, "")
            method_name = convert_event_type_to_method_name.sub(
                "_", method_name
            ).lower()
            event_class = self.event_map.get(event.event_type, None)
            if not event_class:
                logger.warning("Domain event not registered")
                continue
            getattr(aggregate, method_name)(
                event_class(aggregate=aggregate, **event.data)
            )
        return aggregate

    def add_listener(self, projection: Projection):
        self.listeners.append(projection)


class DjangoEventStore(EventStorePersistence):
    def get_event_sequence(self, event: Event) -> int:
        previous_event = (
            StoredEvent.objects.filter(aggregate_id=event.aggregate.id)
            .order_by("-event_sequence")
            .first()
        )
        return previous_event.event_sequence + 1 if previous_event else 1

    def save_event(self, event: StoredEvent):
        event.save()

    def get_aggregate_events(self, aggregate_id: UUID, aggregate_type: type[T]):
        return (
            StoredEvent.objects.filter(aggregate_id=aggregate_id)
            .order_by("event_sequence")
            .all()
        )
