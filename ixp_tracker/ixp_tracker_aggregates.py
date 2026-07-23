from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from ixp_tracker.event_store import DomainEvent, ValueNotChanged, Aggregate


DATE_FORMAT = "%Y-%m-%d %H:%M:%S%z"


@dataclass
class IXPCreated(DomainEvent):
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
class IXPUpdated(DomainEvent):
    name: str | ValueNotChanged = ValueNotChanged()
    long_name: str | ValueNotChanged = ValueNotChanged()
    city: str | ValueNotChanged = ValueNotChanged()
    website: str | ValueNotChanged = ValueNotChanged()
    country_code: str | ValueNotChanged = ValueNotChanged()
    created: str | ValueNotChanged = ValueNotChanged()
    last_updated: str | ValueNotChanged = ValueNotChanged()
    org_id: int | ValueNotChanged = ValueNotChanged()


@dataclass
class ManrsStatusChange(DomainEvent):
    manrs_participant: bool


@dataclass()
class IXPBecameActive(DomainEvent):
    active_status: bool

    def __init__(self, active_status: bool = True):
        if not active_status:
            raise RuntimeError("IXPBecameActive must set status to True")
        self.active_status = True


@dataclass()
class IXPBecameInactive(DomainEvent):
    active_status: bool

    def __init__(self, active_status: bool = False):
        if active_status:
            raise RuntimeError("IXPBecameInactive must set status to False")
        self.active_status = False


@dataclass
class AnchorHostChange(DomainEvent):
    anchor_host: bool


@dataclass
class PhysicalLocationChange(DomainEvent):
    physical_locations: int


@dataclass
class IXPActiveInPeeringDb(DomainEvent):
    last_active: str


@dataclass
class IXPMemberJoined(DomainEvent):
    asn: int
    date_joined: str
    date_updated: str
    last_active: str
    is_rs_peer: bool
    port_speed: int


@dataclass
class PortSpeedUpdated(DomainEvent):
    asn: int
    port_speed: int
    date_updated: str


@dataclass
class IXPMemberActiveInPeeringDb(DomainEvent):
    asn: int
    last_active: str


@dataclass
class RsPeeringStatusChange(DomainEvent):
    asn: int
    is_rs_peer: bool
    date_updated: str


@dataclass
class IXPMemberLeft(DomainEvent):
    asn: int
    date_left: str


@dataclass
class ASNCreated(DomainEvent):
    as_number: int
    name: str
    network_type: str
    peering_policy: str
    peeringdb_id: int
    country_code: str
    nro_status: str
    is_routed: bool
    customer_asns: list[int]


@dataclass
class ASNUpdated(DomainEvent):
    name: str | ValueNotChanged = ValueNotChanged()
    network_type: str | ValueNotChanged = ValueNotChanged()
    peering_policy: str | ValueNotChanged = ValueNotChanged()
    country_code: str | ValueNotChanged = ValueNotChanged()
    nro_status: str | ValueNotChanged = ValueNotChanged()
    is_routed: bool | ValueNotChanged = ValueNotChanged()
    customer_asns: list[int] | ValueNotChanged = ValueNotChanged()


# We don't think this should ever happen but record as a separate event if it does
@dataclass
class ASNPeeringDbIdChanged(DomainEvent):
    peeringdb_id: int


IXP_TRACKER_EVENT_MAP = {
    AnchorHostChange.__name__: AnchorHostChange,
    ASNCreated.__name__: ASNCreated,
    ASNPeeringDbIdChanged.__name__: ASNPeeringDbIdChanged,
    ASNUpdated.__name__: ASNUpdated,
    ManrsStatusChange.__name__: ManrsStatusChange,
    IXPActiveInPeeringDb.__name__: IXPActiveInPeeringDb,
    IXPBecameActive.__name__: IXPBecameActive,
    IXPBecameInactive.__name__: IXPBecameInactive,
    IXPCreated.__name__: IXPCreated,
    IXPUpdated.__name__: IXPUpdated,
    IXPMemberActiveInPeeringDb.__name__: IXPMemberActiveInPeeringDb,
    IXPMemberJoined.__name__: IXPMemberJoined,
    IXPMemberLeft.__name__: IXPMemberLeft,
    PhysicalLocationChange.__name__: PhysicalLocationChange,
    PortSpeedUpdated.__name__: PortSpeedUpdated,
    RsPeeringStatusChange.__name__: RsPeeringStatusChange,
}


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


class NROStatus(Enum):
    ASSIGNED = "assigned"
    AVAILABLE = "available"
    IANAPOOL = "ianapool"
    RESERVED = "reserved"
    UNKNOWN = "unknown"


class ASN(Aggregate):
    name: str
    number: int
    peeringdb_id: int
    # NetworkType is being retired in a future version of PeeringDb so we may need to look for a different source for this
    network_type: NetworkType
    peering_policy: PeeringPolicy
    country_code: str
    nro_status: NROStatus
    is_routed: bool
    customer_asns: list[int]

    def created(self, event: ASNCreated):
        self.name = event.name
        self.number = event.as_number
        self.peeringdb_id = event.peeringdb_id
        self.network_type = NetworkType(event.network_type)
        self.peering_policy = PeeringPolicy(event.peering_policy)
        self.country_code = event.country_code
        self.nro_status = NROStatus(event.nro_status)
        self.is_routed = event.is_routed
        self.customer_asns = event.customer_asns

    def updated(self, event: ASNUpdated):
        if not isinstance(event.name, ValueNotChanged):
            self.name = event.name
        if not isinstance(event.network_type, ValueNotChanged):
            self.network_type = NetworkType(event.network_type)
        if not isinstance(event.peering_policy, ValueNotChanged):
            self.peering_policy = PeeringPolicy(event.peering_policy)
        if not isinstance(event.nro_status, ValueNotChanged):
            self.nro_status = NROStatus(event.nro_status)
        if not isinstance(event.country_code, ValueNotChanged):
            self.country_code = event.country_code

    def peering_db_id_changed(self, event: ASNPeeringDbIdChanged):
        self.peeringdb_id = event.peeringdb_id

    def hydrate(self, data: dict):
        super().hydrate(data)
        self.network_type = NetworkType(self.network_type)
        self.peering_policy = PeeringPolicy(self.peering_policy)
        self.nro_status = NROStatus(self.nro_status)


@dataclass
class IXPMemberDetails:
    date_joined: datetime
    date_updated: datetime
    last_active: datetime
    is_rs_peer: bool
    port_speed: int
    date_left: datetime | None = None


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
    member_history: list[tuple[int, IXPMemberDetails]]

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
        self.member_history = []

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

    def became_active(self, event: IXPBecameActive):
        self.active_status = event.active_status

    def became_inactive(self, event: IXPBecameInactive):
        self.active_status = event.active_status

    def manrs_status_change(self, event: ManrsStatusChange):
        self.manrs_participant = event.manrs_participant

    def anchor_host_change(self, event: AnchorHostChange):
        self.anchor_host = event.anchor_host

    def physical_location_change(self, event: PhysicalLocationChange):
        self.physical_locations = event.physical_locations

    def active_in_peering_db(self, event: IXPActiveInPeeringDb):
        self.last_active = datetime.strptime(event.last_active, DATE_FORMAT)

    def get_members(
        self, include_inactive: bool = False, as_at: datetime | None = None
    ) -> dict[int, IXPMemberDetails]:
        if include_inactive:
            return self.members
        member_list = {}
        if as_at is not None:
            for member_asn in self.members.keys():
                member = self.members[member_asn]
                if member.date_joined <= as_at and (
                    member.date_left is None or member.date_left >= as_at
                ):
                    member_list[member_asn] = member
            for member_asn, member in self.member_history:
                if member.date_joined <= as_at and (
                    member.date_left is None or member.date_left >= as_at
                ):
                    member_list[member_asn] = member
            return member_list
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
        if self.members.get(event.asn) is not None:
            self.member_history.append((event.asn, self.members[event.asn]))
        self.members[event.asn] = details

    def port_speed_updated(self, event: PortSpeedUpdated):
        self.members[event.asn].date_updated = datetime.strptime(
            event.date_updated, DATE_FORMAT
        )
        self.members[event.asn].port_speed = event.port_speed

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

    def hydrate(self, data: dict):
        super().hydrate(data)
        self.date_created = dateify_string(data["date_created"])
        self.last_updated = dateify_string(data["last_updated"])
        self.last_active = dateify_string(data["last_active"])
        members = {}
        for member_asn in self.members.keys():
            member_details = self.members[member_asn]
            members[int(member_asn)] = self.hydrate_member_details(member_details)  # type: ignore
        self.members = members
        self.member_history = []
        for member_asn, member_details in data["member_history"]:
            self.member_history.append(
                (member_asn, self.hydrate_member_details(member_details))
            )

    def hydrate_member_details(
        self, member_details: dict[str, str]
    ) -> IXPMemberDetails:
        return IXPMemberDetails(
            date_joined=dateify_string(member_details["date_joined"]),
            date_updated=dateify_string(member_details["date_updated"]),
            last_active=dateify_string(member_details["last_active"]),
            is_rs_peer=bool(member_details["is_rs_peer"]),
            port_speed=int(member_details["port_speed"]),
            date_left=dateify_string(member_details["date_left"])
            if member_details["date_left"]
            else None,
        )


IXP_TRACKER_AGGREGATE_MAP = {
    "ASN": ASN,
    "IXP": IXP,
}


def stringify_date(date_value: datetime) -> str:
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    return date_value.strftime(DATE_FORMAT)


def dateify_string(string_value: str) -> datetime:
    if "T" in string_value:
        string_value = string_value.replace("T", " ")
    return datetime.strptime(string_value, DATE_FORMAT)


def is_ixp_active(active_members: list) -> bool:
    return len(active_members) >= 3
