from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4, UUID

from ixp_tracker.event_store import (
    EventStore,
    Projection,
    Aggregate,
    Event,
    AggregateNotFound,
    ValueNotChanged,
)
from ixp_tracker.models import StoredEvent, IXPIdMap, IXP as LegacyIXP, ASNMap, IXPASNMemberMap

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


@dataclass
class IXPMemberAdded(Event):
    member_id: str


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
    member_ids: list[UUID] = []

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

    def get_members(self) -> list[UUID]:
        return self.member_ids

    def member_added(self, event: IXPMemberAdded):
        self.member_ids.append(UUID(event.member_id))



class NetworkType(Enum):
    NSP = "NSP"
    CONTENT = "Content"
    CABLE_DSL_ISP = "Cable/DSL/ISP"
    ENTERPRISE = "Enterprise"
    EDUCATION_RESEARCH = "Educational/Research"
    NON_PROFIT = "Non-Profit"
    ROUTE_SERVER = "Route Server"
    NETWORK_SERVICES = "Network Services"
    ROUTE_COLLECTOR = "Route Collector"
    GOVERNMENT = "Government"
    NOT_DISCLOSED = "Not Disclosed"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class PeeringPolicy(Enum):
    OPEN = "Open"
    SELECTIVE = "Selective"
    RESTRICTIVE = "Restrictive"
    NO = "No"
    UNKNOWN = "Unknown"


@dataclass
class ASNCreated(Event):
    as_number: int
    name: str
    network_type: str
    peering_policy: str
    peeringdb_id: int
    country_code: str


@dataclass
class ASNUpdated(Event):
    name: str = ValueNotChanged()
    network_type: str = ValueNotChanged()
    peering_policy: str = ValueNotChanged()
    country_code: str = ValueNotChanged()


# We don't think this should ever happen but record as a separate event if it does
@dataclass
class ASNPeeringDbIdChanged(Event):
    peeringdb_id: int


@dataclass
class IXPMemberCreated(Event):
    ixp_id: str
    asn_id: str
    created_date: str
    updated_date: str
    last_active: str
    is_rs_peer: bool
    port_speed: int


@dataclass
class IXPMemberUpdated(Event):
    created_date: str = ValueNotChanged()
    updated_date: str = ValueNotChanged()
    port_speed: int = ValueNotChanged()


@dataclass
class IXPMemberActiveInPeeringDb(Event):
    last_active: str


@dataclass
class RsPeeringStatusChange(Event):
    is_rs_peer: bool


IXP_TRACKER_EVENT_MAP = {
    AnchorHostChange.__name__: AnchorHostChange,
    ASNCreated.__name__: ASNCreated,
    ASNPeeringDbIdChanged.__name__: ASNPeeringDbIdChanged,
    ASNUpdated.__name__: ASNUpdated,
    ManrsStatusChange.__name__: ManrsStatusChange,
    IXPActiveInPeeringDb.__name__: IXPActiveInPeeringDb,
    IXPCreated.__name__: IXPCreated,
    IXPMemberAdded.__name__: IXPMemberAdded,
    IXPMemberCreated.__name__: IXPMemberCreated,
    IXPMemberUpdated.__name__: IXPMemberUpdated,
    IXPUpdated.__name__: IXPUpdated,
    IXPMemberActiveInPeeringDb.__name__: IXPMemberActiveInPeeringDb,
    PhysicalLocationChange.__name__: PhysicalLocationChange,
    RsPeeringStatusChange.__name__: RsPeeringStatusChange,
}


class ASN(Aggregate):
    name: str
    number: int
    peeringdb_id: int
    # NetworkType is being retired in a future version of PeeringDb so we may need to look for a different source for this
    network_type: NetworkType
    peering_policy: PeeringPolicy
    country_code: str

    def created(self, event: ASNCreated):
        self.name = event.name
        self.number = event.as_number
        self.peeringdb_id = event.peeringdb_id
        self.network_type = NetworkType(event.network_type)
        self.peering_policy = PeeringPolicy(event.peering_policy)
        self.country_code = event.country_code

    def updated(self, event: ASNUpdated):
        if not isinstance(event.name, ValueNotChanged):
            self.name = event.name
        if not isinstance(event.network_type, ValueNotChanged):
            self.network_type = NetworkType(event.network_type)
        if not isinstance(event.peering_policy, ValueNotChanged):
            self.peering_policy = PeeringPolicy(event.peering_policy)
        if not isinstance(event.country_code, ValueNotChanged):
            self.country_code = event.country_code

    def peering_db_id_changed(self, event: ASNPeeringDbIdChanged):
        self.peeringdb_id = event.peeringdb_id


class IXPMember(Aggregate):
    ixp_id: UUID
    asn_id: UUID
    created_date: datetime
    updated_date: datetime
    last_active: datetime
    is_rs_peer: bool
    port_speed: int

    def created(self, event: IXPMemberCreated):
        self.ixp_id = UUID(event.ixp_id)
        self.asn_id = UUID(event.asn_id)
        self.created_date = datetime.strptime(event.created_date, DATE_FORMAT)
        self.updated_date = datetime.strptime(event.updated_date, DATE_FORMAT)
        self.last_active = datetime.strptime(event.last_active, DATE_FORMAT)
        self.is_rs_peer = event.is_rs_peer
        self.port_speed = event.port_speed


    def updated(self, event: IXPMemberUpdated):
        if not isinstance(event.created_date, ValueNotChanged):
            self.created_date = datetime.strptime(event.created_date, DATE_FORMAT)
        if not isinstance(event.updated_date, ValueNotChanged):
            self.updated_date = datetime.strptime(event.updated_date, DATE_FORMAT)
        if not isinstance(event.port_speed, ValueNotChanged):
            self.port_speed = event.port_speed

    def rs_peering_status_change(self, event: RsPeeringStatusChange):
        self.is_rs_peer = event.is_rs_peer

    def active_in_peering_db(self, event: IXPMemberActiveInPeeringDb):
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
            # If a legacy object exists, use that object's primary key as our primary key to preserve the "isoc_id"
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


class ASNList(Projection):
    aggregate_types = [ASN.__name__]
    events = [ASNCreated.__name__]

    def do_handle(self, event: StoredEvent):
        existing = ASNMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        asn = event.data.get("as_number", None)
        asn_map = ASNMap(
            aggregate_id=event.aggregate_id,
            asn=asn,
        )
        asn_map.save()


class MemberMapProjection(Projection):
    aggregate_types = [IXPMember.__name__]
    events = [IXPMemberCreated.__name__]

    def do_handle(self, event: StoredEvent):
        existing = IXPASNMemberMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        asn = event.data.get("as_number", None)
        isoc_id = event.data.get("isoc_id", None)
        member_map = IXPASNMemberMap(
            aggregate_id=event.aggregate_id,
            isoc_id=isoc_id,
            asn=asn,
        )
        member_map.save()


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

    def register_asn(
        self,
        as_number: int,
        name: str,
        network_type: NetworkType,
        peering_policy: PeeringPolicy,
        peeringdb_id: int,
        country_code,
    ):
        asn = ASN(id=uuid4())
        event = ASNCreated(
            asn,
            as_number,
            name,
            network_type.value,
            peering_policy.value,
            peeringdb_id,
            country_code,
        )
        self.es.store(event)
        asn.created(event)
        return asn

    def update_asn(
        self,
        asn: ASN,
        name: str,
        network_type: NetworkType,
        peering_policy: PeeringPolicy,
        peeringdb_id: int,
        country_code: str,
    ):
        updates = {}
        if name != asn.name:
            updates["name"] = name
        if network_type != asn.network_type:
            updates["network_type"] = network_type.value
        if peering_policy != asn.peering_policy:
            updates["peering_policy"] = peering_policy.value
        if country_code != asn.country_code:
            updates["country_code"] = country_code
        if len(updates.keys()) > 0:
            event = ASNUpdated(asn, **updates)
            self.es.store(event)
            asn.updated(event)
        if peeringdb_id != asn.peeringdb_id:
            event = ASNPeeringDbIdChanged(asn, peeringdb_id=peeringdb_id)
            self.es.store(event)
            asn.peering_db_id_changed(event)
        return asn

    def register_member(
        self,
        ixp: IXP,
        as_number: int,
        created_date: datetime,
        updated_date: datetime,
        processing_date: datetime,
        is_rs_peer: bool,
        port_speed: int,
    ):
        as_entity = self.get_asn(as_number)
        if as_entity is None:
            return None
        member = IXPMember(id=uuid4())
        event = IXPMemberCreated(
            member,
            str(ixp.id),
            str(as_entity.id),
            stringify_date(created_date),
            stringify_date(updated_date),
            stringify_date(processing_date),
            is_rs_peer,
            port_speed,
        )
        self.es.store(event)
        member.created(event)
        event = IXPMemberAdded(ixp, str(member.id))
        self.es.store(event)
        ixp.member_added(event)
        return member

    def update_member(
        self,
        member: IXPMember,
        created_date: datetime,
        updated_date: datetime,
        processing_date: datetime,
        is_rs_peer: bool,
        port_speed: int,
    ):
        updates = {}
        if created_date != member.created_date:
            updates["created_date"] = stringify_date(created_date)
        if updated_date != member.updated_date:
            updates["updated_date"] = stringify_date(updated_date)
        if port_speed != member.port_speed:
            updates["port_speed"] = port_speed
        if len(updates.keys()) > 0:
            event = IXPMemberUpdated(member, **updates)
            self.es.store(event)
            member.updated(event)
        if member.is_rs_peer != is_rs_peer:
            rs_peer_update = RsPeeringStatusChange(member, is_rs_peer=is_rs_peer)
            self.es.store(rs_peer_update)
            member.rs_peering_status_change(rs_peer_update)
        event = IXPMemberActiveInPeeringDb(member, last_active=stringify_date(processing_date))
        self.es.store(event)
        member.active_in_peering_db(event)
        return member

    def find_by_peeringdb_id(self, peeringdb_id: int) -> IXP | None:
        try:
            id_map = IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
            return self.es.get_aggregate(id_map.aggregate_id, IXP)
        except (IXPIdMap.DoesNotExist, AggregateNotFound):
            return None

    def get_all_ixps(self):
        return self.es.get_all(IXP)

    def get_all_asns(self):
        return self.es.get_all(ASN)

    def get_asn(self, asn) -> ASN | None:
        try:
            asn_map = ASNMap.objects.get(asn=asn)
            return self.es.get_aggregate(asn_map.aggregate_id, ASN)
        except ASNMap.DoesNotExist:
            return None

    def get_all_members(self):
        return self.es.get_all(IXPMember)

    def get_member(self, isoc_id: int, asn: int) -> IXPMember | None:
        try:
            member_map = IXPASNMemberMap.objects.get(isoc_id=isoc_id, asn=asn)
            return self.es.get_aggregate(member_map.aggregate_id, IXPMember)
        except IXPASNMemberMap.DoesNotExist:
            return None

def stringify_date(date_value: datetime) -> str:
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    return date_value.strftime(DATE_FORMAT)
