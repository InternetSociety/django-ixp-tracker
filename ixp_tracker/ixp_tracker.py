from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import TypedDict, Any
from uuid import uuid4

from ixp_tracker.data_lookup import ASNGeoLookup
from ixp_tracker.event_store import (
    EventStore,
    Projection,
    Aggregate,
    Event,
    AggregateNotFound,
    ValueNotChanged,
)
from ixp_tracker.models import StoredEvent, IXPIdMap, IXP as LegacyIXP, ASNMap

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
    physical_locations: int | None = None


@dataclass
class IXPUpdated(Event):
    name: str | ValueNotChanged = ValueNotChanged()
    long_name: str | ValueNotChanged = ValueNotChanged()
    city: str | ValueNotChanged = ValueNotChanged()
    website: str | ValueNotChanged = ValueNotChanged()
    country_code: str | ValueNotChanged = ValueNotChanged()
    created: str | ValueNotChanged = ValueNotChanged()
    last_updated: str | ValueNotChanged = ValueNotChanged()
    org_id: int | ValueNotChanged = ValueNotChanged()


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
class IXPMemberDetails:
    date_joined: datetime
    date_updated: datetime
    last_active: datetime
    is_rs_peer: bool
    port_speed: int
    date_left: datetime | None = None


@dataclass
class IXPMemberJoined(Event):
    asn: int
    date_joined: str
    date_updated: str
    last_active: str
    is_rs_peer: bool
    port_speed: int


@dataclass
class IXPMemberUpdated(Event):
    asn: int
    date_joined: str | ValueNotChanged = ValueNotChanged()
    date_left: str | ValueNotChanged = ValueNotChanged()
    date_updated: str | ValueNotChanged = ValueNotChanged()
    port_speed: int | ValueNotChanged = ValueNotChanged()


@dataclass
class IXPMemberActiveInPeeringDb(Event):
    asn: int
    last_active: str


@dataclass
class RsPeeringStatusChange(Event):
    asn: int
    is_rs_peer: bool


@dataclass
class IXPMemberLeft(Event):
    asn: int
    date_left: str


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
    members: dict[int, IXPMemberDetails]

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
        self.members = {}

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

    def get_members(
        self, include_inactive: bool = False
    ) -> dict[int, IXPMemberDetails]:
        if include_inactive:
            return self.members
        member_list = {}
        for member_asn in self.members.keys():
            member = self.members[member_asn]
            if member.date_left is None:
                member_list[member_asn] = member
        return member_list

    def member_joined(self, event: IXPMemberJoined):
        details = IXPMemberDetails(
            datetime.strptime(event.date_joined, DATE_FORMAT),
            datetime.strptime(event.date_updated, DATE_FORMAT),
            datetime.strptime(event.last_active, DATE_FORMAT),
            event.is_rs_peer,
            event.port_speed,
        )
        self.members[event.asn] = details

    def member_updated(self, event: IXPMemberUpdated):
        if not isinstance(event.date_joined, ValueNotChanged):
            self.members[event.asn].date_joined = datetime.strptime(
                event.date_joined, DATE_FORMAT
            )
        if not isinstance(event.date_updated, ValueNotChanged):
            self.members[event.asn].date_updated = datetime.strptime(
                event.date_updated, DATE_FORMAT
            )
        if not isinstance(event.port_speed, ValueNotChanged):
            self.members[event.asn].port_speed = event.port_speed
        if not isinstance(event.date_left, ValueNotChanged):
            self.members[event.asn].date_left = None

    def member_active_in_peering_db(self, event: IXPMemberActiveInPeeringDb):
        self.members[event.asn].last_active = datetime.strptime(
            event.last_active, DATE_FORMAT
        )

    def rs_peering_status_change(self, event: RsPeeringStatusChange):
        self.members[event.asn].is_rs_peer = event.is_rs_peer

    def member_left(self, event: IXPMemberLeft):
        self.members[event.asn].date_left = datetime.strptime(
            event.date_left, DATE_FORMAT
        )


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
    name: str | ValueNotChanged = ValueNotChanged()
    network_type: str | ValueNotChanged = ValueNotChanged()
    peering_policy: str | ValueNotChanged = ValueNotChanged()
    country_code: str | ValueNotChanged = ValueNotChanged()


# We don't think this should ever happen but record as a separate event if it does
@dataclass
class ASNPeeringDbIdChanged(Event):
    peeringdb_id: int


IXP_TRACKER_EVENT_MAP = {
    AnchorHostChange.__name__: AnchorHostChange,
    ASNCreated.__name__: ASNCreated,
    ASNPeeringDbIdChanged.__name__: ASNPeeringDbIdChanged,
    ASNUpdated.__name__: ASNUpdated,
    ManrsStatusChange.__name__: ManrsStatusChange,
    IXPActiveInPeeringDb.__name__: IXPActiveInPeeringDb,
    IXPCreated.__name__: IXPCreated,
    IXPUpdated.__name__: IXPUpdated,
    IXPMemberActiveInPeeringDb.__name__: IXPMemberActiveInPeeringDb,
    IXPMemberJoined.__name__: IXPMemberJoined,
    IXPMemberLeft.__name__: IXPMemberLeft,
    IXPMemberUpdated.__name__: IXPMemberUpdated,
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
                id=preserve_legacy_id.pk,
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
            return None


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


class MemberImportData(TypedDict):
    asn: int
    created_date: datetime
    updated_date: datetime
    # TODO We're already passing in the processing_date separately so perhaps we should remove this here and just use that
    last_active: datetime
    is_rs_peer: bool
    port_speed: int


class IXPTracker:
    es: EventStore
    # TODO We only need the ASN lookup for now but we should probably move the other lookups into the app too (e.g. MANRS, RIPE Anchors)
    geo_lookup: ASNGeoLookup

    def __init__(self, es: EventStore, geo_lookup: ASNGeoLookup):
        self.es = es
        self.geo_lookup = geo_lookup

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
        updates: dict[str, Any] = {}
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
            anchor_host_event = AnchorHostChange(ixp, anchor_host=anchor_host)
            self.es.store(anchor_host_event)
            ixp.anchor_host_change(anchor_host_event)
        if (
            ixp.physical_locations != physical_locations
            and physical_locations is not None
        ):
            locations_event = PhysicalLocationChange(
                ixp, physical_locations=physical_locations
            )
            self.es.store(locations_event)
            ixp.physical_location_change(locations_event)
        active_event = IXPActiveInPeeringDb(
            ixp, last_active=stringify_date(last_active)
        )
        self.es.store(active_event)
        ixp.active_in_peering_db(active_event)
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
            peering_id_event = ASNPeeringDbIdChanged(asn, peeringdb_id=peeringdb_id)
            self.es.store(peering_id_event)
            asn.peering_db_id_changed(peering_id_event)
        return asn

    def import_members(
        self,
        ixp: IXP,
        ixp_data: list[MemberImportData],
        processing_date: datetime,
    ):
        existing_members = ixp.get_members(True)
        for member in ixp_data:
            as_entity = self.get_asn(member["asn"])
            if as_entity is None:
                continue
            existing_member = existing_members.get(member["asn"])
            member_has_rejoined = (
                existing_member
                and existing_member.date_left is not None
                and existing_member.date_left < member["created_date"]
            )
            if existing_member is None or member_has_rejoined:
                join_event = IXPMemberJoined(
                    ixp,
                    member["asn"],
                    stringify_date(member["created_date"]),
                    stringify_date(member["updated_date"]),
                    stringify_date(member["last_active"]),
                    member["is_rs_peer"],
                    member["port_speed"],
                )
                self.es.store(join_event)
                ixp.member_joined(join_event)
            else:
                updates: dict[str, Any] = {}
                # If we already have an inactive member, but it's end_date is after the start_date we're importing,
                # then we just unset the end_date, which makes the member active and keeps the original start_date
                if (
                    existing_member.date_left is not None
                    and existing_member.date_left > member["created_date"]
                ):
                    updates["date_left"] = None
                elif member["created_date"] != existing_member.date_joined:
                    updates["date_joined"] = stringify_date(member["created_date"])
                if member["updated_date"] != existing_member.date_updated:
                    updates["date_updated"] = stringify_date(member["updated_date"])
                if member["port_speed"] != existing_member.port_speed:
                    updates["port_speed"] = member["port_speed"]
                if len(updates.keys()) > 0:
                    update_event = IXPMemberUpdated(ixp, member["asn"], **updates)
                    self.es.store(update_event)
                    ixp.member_updated(update_event)
                if member["is_rs_peer"] != existing_member.is_rs_peer:
                    rs_peer_event = RsPeeringStatusChange(
                        ixp, member["asn"], member["is_rs_peer"]
                    )
                    self.es.store(rs_peer_event)
                    ixp.rs_peering_status_change(rs_peer_event)
                active_event = IXPMemberActiveInPeeringDb(
                    ixp, member["asn"], stringify_date(member["last_active"])
                )
                self.es.store(active_event)
                ixp.member_active_in_peering_db(active_event)

        members = ixp.get_members()
        members_left = check_if_members_have_left(
            members, processing_date, self.geo_lookup
        )
        for member_left in members_left:
            left_event = IXPMemberLeft(
                ixp, member_left[0], stringify_date(member_left[1])
            )
            self.es.store(left_event)
            ixp.member_left(left_event)
        return ixp

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


def stringify_date(date_value: datetime) -> str:
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    return date_value.strftime(DATE_FORMAT)


def check_if_members_have_left(
    members: dict[int, IXPMemberDetails],
    processing_date: datetime,
    geo_lookup: ASNGeoLookup,
) -> list[tuple[int, datetime]]:
    start_of_month = processing_date.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    members_left: list[tuple[int, datetime]] = []
    for member_asn in members.keys():
        member = members[member_asn]
        if member.last_active < start_of_month:
            start_of_month_after_last_active = (
                member.last_active.replace(day=1) + timedelta(days=33)
            ).replace(day=1)
            end_of_month = start_of_month_after_last_active - timedelta(days=1)
            members_left.append((member_asn, end_of_month))
        if (
            member.date_left is None
            and geo_lookup.get_iso2_country(member_asn, processing_date) == "ZZ"
            and geo_lookup.get_status(member_asn, processing_date) != "assigned"
        ):
            end_of_last_month_active = member.last_active.replace(day=1) - timedelta(
                days=1
            )
            members_left.append((member_asn, end_of_last_month_active))
    return members_left
