import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID

# At some point we might want to change the ES persistence to depend on a neutral DTO rather than this Django model
from ixp_tracker.models import StoredEvent, AggregateSnapshot

logger = logging.getLogger("ixp_tracker")

convert_event_type_to_method_name = re.compile(r"(?<!^)(?=[A-Z])")


@dataclass
class DomainEvent(ABC):
    pass


@dataclass
class Aggregate(ABC):
    id: UUID
    sequence: int = 0

    def hydrate(self, data: dict):
        for key in data.keys():
            setattr(self, key, data[key])

    def snapshot(self):
        values = dict(self.__dict__)
        del values["id"]
        return values

    def apply_event(self, event: DomainEvent, sequence: int):
        method_name = type(event).__name__.replace(type(self).__name__, "")
        method_name = convert_event_type_to_method_name.sub("_", method_name).lower()
        self.sequence = sequence
        getattr(self, method_name)(event)


T = TypeVar("T", bound=Aggregate)


class ValueNotChanged:
    pass


class EventHasNoUpdatedFields(Exception):
    pass


class AggregateNotFound(Exception):
    pass


class EventNotMapped(Exception):
    pass


class EventOrderInvalid(Exception):
    pass


class Projection(ABC):
    def __init__(self):
        if self.__getattribute__("aggregate_types") is None:
            self.aggregate_types = []
        if self.__getattribute__("events") is None:
            self.events = []

    def handle(self, event: StoredEvent, aggregate: T):
        if event.aggregate_type not in self.aggregate_types:
            return
        if event.event_type not in self.events:
            return
        self.do_handle(event, aggregate)

    def do_handle(self, event: StoredEvent, aggregate: T):
        pass


class EventStorePersistence(ABC):
    @abstractmethod
    def get_event_sequence(self, event: DomainEvent, aggregate_id: UUID) -> int:
        pass

    @abstractmethod
    def save_event(self, event: StoredEvent):
        pass

    @abstractmethod
    def get_aggregate_events(
        self,
        aggregate_id: UUID,
        aggregate_type: type[T],
        sequence: int | None,
        as_at: datetime | None = None,
    ) -> list[StoredEvent]:
        pass

    @abstractmethod
    def get_all(
        self, aggregate_type: type[T], as_at: datetime | None = None
    ) -> list[UUID]:
        pass

    @abstractmethod
    def get_events(self) -> list[StoredEvent]:
        pass

    @abstractmethod
    def save_snapshot(
        self, aggregate_id: UUID, data: dict, sequence: int, date_now: datetime
    ):
        pass

    @abstractmethod
    def load_snapshot(
        self, aggregate_id: UUID, as_at: datetime | None = None
    ) -> tuple[dict, int] | tuple[None, None]:
        pass


class EventStore:
    def __init__(self, event_map, db: EventStorePersistence):
        self.listeners: list[Projection] = []
        self.event_map: dict[str, type[DomainEvent]] = event_map
        self.db: EventStorePersistence = db
        self.date_now: datetime | None = None

    def time_travel(self, date_in_past: datetime | None):
        self.date_now = date_in_past

    def store(self, aggregate: T, event: DomainEvent) -> T:
        event_sequence = self.db.get_event_sequence(event, aggregate.id)
        event_data = asdict(event)
        event_data = {
            key: value
            for key, value in event_data.items()
            if key not in ["aggregate"] and not isinstance(value, ValueNotChanged)
        }
        if len(event_data.keys()) == 0:
            raise EventHasNoUpdatedFields

        stored_event = StoredEvent(
            aggregate_id=aggregate.id,
            aggregate_type=type(aggregate).__name__,
            event_date=self.date_now or datetime.now(timezone.utc),
            event_type=type(event).__name__,
            event_sequence=event_sequence,
            data=event_data,
        )
        self.db.save_event(stored_event)
        aggregate.apply_event(event, stored_event.event_sequence)
        for listener in self.listeners:
            listener.handle(stored_event, aggregate)

        return aggregate

    def get_aggregate(
        self, aggregate_id: UUID, aggregate_type: type[T], as_at: datetime | None = None
    ) -> T:
        data, sequence = self.db.load_snapshot(aggregate_id, as_at)
        aggregate = aggregate_type(aggregate_id)
        if data:
            aggregate.hydrate(data)
        events = self.db.get_aggregate_events(
            aggregate_id, aggregate_type, sequence, as_at
        )
        if sequence is None and len(events) == 0:
            raise AggregateNotFound
        for event in events:
            if event.event_sequence != (aggregate.sequence + 1):
                raise EventOrderInvalid(
                    f"Domain event out of order, aggregate {aggregate.sequence}, event:{event.event_sequence}"
                )
            event_class = self.event_map.get(event.event_type, None)
            if not event_class:
                raise EventNotMapped("Domain event not registered")
            aggregate.apply_event(
                event_class(**event.data),
                event.event_sequence,
            )
        return aggregate

    def get_all(
        self, aggregate_type: type[T], as_at: datetime | None = None
    ) -> list[T]:
        aggregate_ids = self.db.get_all(aggregate_type, as_at)
        aggregates = []
        for aggregate_id in aggregate_ids:
            aggregates.append(self.get_aggregate(aggregate_id, aggregate_type, as_at))
        return aggregates

    def add_listener(self, projection: Projection):
        self.listeners.append(projection)

    def save_snapshot(self, aggregate: T):
        self.db.save_snapshot(
            aggregate.id,
            aggregate.snapshot(),
            aggregate.sequence,
            self.date_now or datetime.now(timezone.utc),
        )

    def load_snapshot(self, aggregate_id: UUID, aggregate_type: type[T]) -> T | None:
        data, _ = self.db.load_snapshot(aggregate_id)
        if data is None:
            return None
        aggregate = aggregate_type(aggregate_id)
        aggregate.hydrate(data)
        return aggregate


class DjangoEventStore(EventStorePersistence):
    def get_event_sequence(self, event: DomainEvent, aggregate_id: UUID) -> int:
        previous_event = (
            StoredEvent.objects.filter(aggregate_id=aggregate_id)
            .order_by("-event_sequence")
            .first()
        )
        return previous_event.event_sequence + 1 if previous_event else 1

    def save_event(self, event: StoredEvent):
        event.save()

    def get_aggregate_events(
        self,
        aggregate_id: UUID,
        aggregate_type: type[T],
        sequence: int | None,
        as_at: datetime | None = None,
    ):
        events = StoredEvent.objects.filter(aggregate_id=aggregate_id)
        if sequence is not None:
            events = events.filter(event_sequence__gt=sequence)
        if as_at is not None:
            events = events.filter(event_date__lte=as_at)
        return events.order_by("event_sequence").all()

    def get_all(
        self, aggregate_type: type[T], as_at: datetime | None = None
    ) -> list[UUID]:
        aggregate_ids = StoredEvent.objects.filter(
            aggregate_type=aggregate_type.__name__
        )
        if as_at is not None:
            aggregate_ids = aggregate_ids.filter(event_date__lte=as_at)
        return list(aggregate_ids.values_list("aggregate_id", flat=True).distinct())

    def get_events(self) -> list[StoredEvent]:
        return list(StoredEvent.objects.all())

    def save_snapshot(
        self, aggregate_id: UUID, data: dict, sequence: int, date_now: datetime
    ):
        AggregateSnapshot.objects.update_or_create(
            aggregate_id=aggregate_id,
            event_sequence=sequence,
            defaults={"data": data, "snapshot_date": date_now},
        )

    def load_snapshot(
        self, aggregate_id: UUID, as_at: datetime | None = None
    ) -> tuple[dict, int] | tuple[None, None]:
        snapshots = AggregateSnapshot.objects.filter(aggregate_id=aggregate_id)
        if as_at is not None:
            snapshots = snapshots.filter(snapshot_date__lte=as_at)
        snapshot = snapshots.first()
        if snapshot is None:
            return None, None
        else:
            return snapshot.data, snapshot.event_sequence
