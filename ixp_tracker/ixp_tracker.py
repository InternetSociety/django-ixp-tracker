from dataclasses import dataclass
from uuid import uuid4

from ixp_tracker.event_store import EventStore, Projection, Aggregate, Event
from ixp_tracker.models import StoredEvent, ISOCId


class ISOCIdProjection(Projection):
    def handle(self, event: StoredEvent):
        isoc_id = ISOCId(aggregate_id=event.aggregate_id)
        isoc_id.save()


class IXPTracker:
    es: EventStore
    isoc_ids: ISOCIdProjection

    def __init__(self, es: EventStore, isoc_ids: ISOCIdProjection):
        self.es = es
        self.es.add_listener(isoc_ids)
        self.isoc_ids = isoc_ids

    def register_ixp(self, name, long_name, city, peeringdb_id):
        ixp = IXP(id=uuid4())
        event = IXPCreated(ixp, name, long_name, city, peeringdb_id)
        self.es.store(event)
        ixp.created(name, long_name, city, peeringdb_id)
        return ixp


class IXP(Aggregate):
    name: str
    long_name: str
    city: str
    peeringdb_id: int

    def created(
        self,
        name: str,
        long_name: str,
        city: str,
        peeringdb_id: int,
    ):
        self.name = name
        self.long_name = long_name
        self.city = city
        self.peeringdb_id = peeringdb_id


@dataclass
class IXPCreated(Event):
    name: str
    long_name: str
    city: str
    peeringdb_id: int
