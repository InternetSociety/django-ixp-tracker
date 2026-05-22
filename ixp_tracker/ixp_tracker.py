from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from ixp_tracker.event_store import (
    EventStore,
    Projection,
    Aggregate,
    Event,
    AggregateNotFound,
    ValueNotChanged,
)
from ixp_tracker.models import StoredEvent, IXPIdMap, IXP as LegacyIXP

DATE_FORMAT = "%Y-%m-%d %H:%M:%S%z"


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
    physical_locations: int = None


@dataclass
class IXPUpdated(Event):
    name: str = ValueNotChanged()
    long_name: str = ValueNotChanged()
    city: str = ValueNotChanged()
    website: str = ValueNotChanged()
    country_code: str = ValueNotChanged()
    created: str = ValueNotChanged()
    last_updated: str = ValueNotChanged()
    org_id: int = ValueNotChanged()


@dataclass
class ManrsStatusChange(Event):
    manrs_participant: bool


@dataclass
class AnchorHostChange(Event):
    anchor_host: bool


@dataclass
class PhysicalLocationChange(Event):
    physical_locations: int


@dataclass
class IXPActiveInPeeringDb(Event):
    last_active: str


IXP_TRACKER_EVENT_MAP = {
    AnchorHostChange.__name__: AnchorHostChange,
    ManrsStatusChange.__name__: ManrsStatusChange,
    IXPActiveInPeeringDb.__name__: IXPActiveInPeeringDb,
    IXPCreated.__name__: IXPCreated,
    IXPUpdated.__name__: IXPUpdated,
    PhysicalLocationChange.__name__: PhysicalLocationChange,
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
    physical_locations: int | None

    def created(self, event: IXPCreated):
        self.name = event.name
        self.long_name = event.long_name
        self.city = event.city
        self.peeringdb_id = event.peeringdb_id
        self.website = event.website
        self.active_status = event.active_status
        self.country_code = event.country_code
        self.date_created = datetime.strptime(event.created, DATE_FORMAT)
        self.last_updated = datetime.strptime(event.last_updated, DATE_FORMAT)
        self.last_active = datetime.strptime(event.last_active, DATE_FORMAT)
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
            self.date_created = datetime.strptime(event.created, DATE_FORMAT)
        if not isinstance(event.last_updated, ValueNotChanged):
            self.last_updated = datetime.strptime(event.last_updated, DATE_FORMAT)
        if not isinstance(event.org_id, ValueNotChanged):
            self.org_id = event.org_id

    def manrs_status_change(self, event: ManrsStatusChange):
        self.manrs_participant = event.manrs_participant

    def anchor_host_change(self, event: AnchorHostChange):
        self.anchor_host = event.anchor_host

    def physical_location_change(self, event: PhysicalLocationChange):
        self.physical_locations = event.physical_locations

    def active_in_peering_db(self, event: IXPActiveInPeeringDb):
        self.last_active = datetime.strptime(event.last_active, DATE_FORMAT)


class IXPIdMapProjection(Projection):
    aggregate_types = [IXP.__name__]
    events = [IXPCreated.__name__]

    def do_handle(self, event: StoredEvent):
        existing = IXPIdMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        peeringdb_id = event.data.get("peeringdb_id", None)
        preserve_legacy_id = LegacyIXP.objects.filter(peeringdb_id=peeringdb_id).first()
        if preserve_legacy_id:
            # If a legacy object exists, use that's primary key as our primary key to preserve the "isoc_id"
            isoc_id = IXPIdMap(
                id=preserve_legacy_id.id,
                aggregate_id=event.aggregate_id,
                peeringdb_id=peeringdb_id,
            )
        else:
            isoc_id = IXPIdMap(
                aggregate_id=event.aggregate_id,
                peeringdb_id=peeringdb_id,
            )
        isoc_id.save()

    def find_by_peeringdb_id(self, peeringdb_id: int) -> IXPIdMap | None:
        try:
            return IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
        except IXPIdMap.DoesNotExist:
            return


class IXPTracker:
    es: EventStore

    def __init__(self, es: EventStore):
        self.es = es

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
            stringify_date(created),
            stringify_date(last_updated),
            stringify_date(last_active),
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
        ixp: IXP,
        name: str,
        long_name: str,
        city: str,
        website: str,
        country_code: str,
        created: datetime,
        last_updated: datetime,
        last_active: datetime,
        org_id: int,
        manrs_participant: bool,
        anchor_host: bool,
        physical_locations: int | None,
    ):
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
            updates["created"] = stringify_date(created)
        if last_updated != ixp.last_updated:
            updates["last_updated"] = stringify_date(last_updated)
        if org_id != ixp.org_id:
            updates["org_id"] = org_id
        if len(updates.keys()) > 0:
            event = IXPUpdated(ixp, **updates)
            self.es.store(event)
            ixp.updated(event)
        if ixp.manrs_participant != manrs_participant:
            manrs_update = ManrsStatusChange(ixp, manrs_participant=manrs_participant)
            self.es.store(manrs_update)
            ixp.manrs_status_change(manrs_update)
        if ixp.anchor_host != anchor_host:
            event = AnchorHostChange(ixp, anchor_host=anchor_host)
            self.es.store(event)
            ixp.anchor_host_change(event)
        if (
            ixp.physical_locations != physical_locations
            and physical_locations is not None
        ):
            event = PhysicalLocationChange(ixp, physical_locations=physical_locations)
            self.es.store(event)
            ixp.physical_location_change(event)
        event = IXPActiveInPeeringDb(ixp, last_active=stringify_date(last_active))
        self.es.store(event)
        ixp.active_in_peering_db(event)
        return ixp

    def find_by_peeringdb_id(self, peeringdb_id: int) -> IXP | None:
        try:
            id_map = IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
            return self.es.get_aggregate(id_map.aggregate_id, IXP)
        except (IXPIdMap.DoesNotExist, AggregateNotFound):
            return None

    def get_all_ixps(self):
        return self.es.get_all(IXP)


def stringify_date(date_value: datetime) -> str:
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    return date_value.strftime(DATE_FORMAT)
