import logging
import re
from abc import ABC
from dataclasses import dataclass, asdict
from typing import TypeVar
from uuid import UUID

# At some point we might want to extract a storage mechanism for events so that everything here just depends on a neutral DTO
# But we probably don't need that complication right now as all our projections will be using Django anyway
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


class EventStore(ABC):
    listeners: list[Projection]
    event_map: dict[str, type[Event]]

    def __init__(self, event_map):
        self.listeners = []
        self.event_map = event_map

    def store(self, event: Event) -> StoredEvent:
        pass

    def get_aggregate(self, aggregate_id: UUID, aggregate_type: type[T]) -> T:
        pass

    def add_listener(self, projection: Projection):
        self.listeners.append(projection)


class DjangoEventStore(EventStore):
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

    def get_aggregate(self, aggregate_id: UUID, aggregate_type: type[T]) -> T:
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
            event_class = self.event_map.get(event.event_type, None)
            if not event_class:
                logger.warning("Domain event not registered")
                continue
            getattr(aggregate, method_name)(
                event_class(aggregate=aggregate, **event.data)
            )
        return aggregate
