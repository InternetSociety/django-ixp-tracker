from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4, UUID

from ixp_tracker.event_store import (
    EventStore,
    Projection,
    Aggregate,
    Event,
    AggregateNotFound,
    ValueNotChanged,
)
from ixp_tracker.models import StoredEvent, IXPIdMap


@dataclass
class IXPCreated(Event):
    name: str
    long_name: str
    city: str
    peeringdb_id: int
    website: str
    active_status: bool
    country_code: str
    created: str
    last_updated: str
    last_active: str
    manrs_participant: bool
    anchor_host: bool
    org_id: int
    physical_locations: int


@dataclass
class IXPUpdated(Event):
    name: str = ValueNotChanged()
    long_name: str = ValueNotChanged()
    city: str = ValueNotChanged()
    website: str = ValueNotChanged()
    country_code: str = ValueNotChanged()
    created: str = ValueNotChanged()
    last_updated: str = ValueNotChanged()
    last_active: str = ValueNotChanged()
    org_id: int = ValueNotChanged()


IXP_TRACKER_EVENT_MAP = {
    "IXPCreated": IXPCreated,
    "IXPUpdated": IXPUpdated,
}


class IXP(Aggregate):
    name: str
    long_name: str
    city: str
    peeringdb_id: int
    website: str
    active_status: bool = True
    country_code: str
    date_created: datetime
    last_updated: datetime
    last_active: datetime
    manrs_participant: bool = False
    anchor_host: bool = False
    org_id: int
    physical_locations: int

    def created(self, event: IXPCreated):
        self.name = event.name
        self.long_name = event.long_name
        self.city = event.city
        self.peeringdb_id = event.peeringdb_id
        self.website = event.website
        self.active_status = event.active_status
        self.country_code = event.country_code
        self.date_created = datetime.strptime(event.created, "%Y-%m-%d %H:%M:%S.%f%z")
        self.last_updated = datetime.strptime(
            event.last_updated, "%Y-%m-%d %H:%M:%S.%f%z"
        )
        self.last_active = datetime.strptime(
            event.last_active, "%Y-%m-%d %H:%M:%S.%f%z"
        )
        self.manrs_participant = event.manrs_participant
        self.anchor_host = event.anchor_host
        self.org_id = event.org_id
        self.physical_locations = event.physical_locations

    def updated(self, event: IXPUpdated):
        if not isinstance(event.name, ValueNotChanged):
            self.name = event.name
        if not isinstance(event.long_name, ValueNotChanged):
            self.long_name = event.long_name
        if not isinstance(event.city, ValueNotChanged):
            self.city = event.city
        if not isinstance(event.website, ValueNotChanged):
            self.website = event.website
        if not isinstance(event.country_code, ValueNotChanged):
            self.country_code = event.country_code
        if not isinstance(event.created, ValueNotChanged):
            self.date_created = datetime.strptime(
                event.created, "%Y-%m-%d %H:%M:%S.%f%z"
            )
        if not isinstance(event.last_updated, ValueNotChanged):
            self.last_updated = datetime.strptime(
                event.last_updated, "%Y-%m-%d %H:%M:%S.%f%z"
            )
        if not isinstance(event.last_active, ValueNotChanged):
            self.last_active = datetime.strptime(
                event.last_active, "%Y-%m-%d %H:%M:%S.%f%z"
            )
        if not isinstance(event.org_id, ValueNotChanged):
            self.org_id = event.org_id


class IXPIdMapProjection(Projection):
    aggregate_types = [IXP.__name__]
    events = [IXPCreated.__name__]

    def do_handle(self, event: StoredEvent):
        existing = IXPIdMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        isoc_id = IXPIdMap(
            aggregate_id=event.aggregate_id,
            peeringdb_id=event.data.get("peeringdb_id", None),
        )
        isoc_id.save()

    def find_by_peeringdb_id(self, peeringdb_id: int) -> IXPIdMap | None:
        try:
            return IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
        except IXPIdMap.DoesNotExist:
            return


class IXPTracker:
    es: EventStore
    isoc_ids: IXPIdMapProjection

    def __init__(self, es: EventStore, isoc_ids: IXPIdMapProjection):
        self.es = es
        self.es.add_listener(isoc_ids)
        self.isoc_ids = isoc_ids

    def register_ixp(
        self,
        name: str,
        long_name: str,
        city: str,
        peeringdb_id: int,
        website: str,
        country_code: str,
        created: datetime,
        last_updated: datetime,
        last_active: datetime,
        manrs_participant: bool,
        anchor_host: bool,
        org_id: int,
        physical_locations: int,
    ):
        active_status = True
        ixp = IXP(id=uuid4())
        event = IXPCreated(
            ixp,
            name,
            long_name,
            city,
            peeringdb_id,
            website,
            active_status,
            country_code,
            str(created),
            str(last_updated),
            str(last_active),
            manrs_participant,
            anchor_host,
            org_id,
            physical_locations,
        )
        self.es.store(event)
        ixp.created(event)
        return ixp

    def update_ixp(
        self,
        aggregate_id: UUID,
        name: str,
        long_name: str,
        city: str,
        website: str,
        country_code: str,
        created: datetime,
        last_updated: datetime,
        last_active: datetime,
        org_id: int,
    ):
        ixp = self.es.get_aggregate(aggregate_id, IXP)
        updates = {}
        if name != ixp.name:
            updates["name"] = name
        if long_name != ixp.long_name:
            updates["long_name"] = long_name
        if city != ixp.city:
            updates["city"] = city
        if website != ixp.website:
            updates["website"] = website
        if country_code != ixp.country_code:
            updates["country_code"] = country_code
        if created != ixp.date_created:
            updates["created"] = str(created)
        if last_updated != ixp.last_updated:
            updates["last_updated"] = str(last_updated)
        if last_active != ixp.last_active:
            updates["last_active"] = str(last_active)
        if org_id != ixp.org_id:
            updates["org_id"] = org_id
        event = IXPUpdated(ixp, **updates)
        self.es.store(event)
        ixp.updated(event)
        # @TODO handle updates to
        # manrs_participant: bool,
        # anchor_host: bool,
        # physical_locations: int,
        return ixp

    def find_by_peeringdb_id(self, peeringdb_id: int) -> IXP | None:
        try:
            id_map = IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
            return self.es.get_aggregate(id_map.aggregate_id, IXP)
        except (IXPIdMap.DoesNotExist, AggregateNotFound):
            return None
