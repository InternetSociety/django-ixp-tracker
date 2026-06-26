from datetime import date
from typing import Optional, TypedDict


class ASNRecord(TypedDict):
    holder_name: str
    asn: int
    network_type: str
    registration_country: str
    peering_policy: str


class IXPMemberRecord(TypedDict):
    asn: ASNRecord
    member_since: date
    speed: int
    is_rs_peer: bool


class IXPRecord(TypedDict):
    isoc_id: int
    name: str
    long_name: str
    country: str
    city: str
    website: str
    last_updated: Optional[date]
    members: list[IXPMemberRecord]
    peering_id: int
    active: bool
    manrs_participant: bool
    anchor_host: bool
    physical_locations: int
