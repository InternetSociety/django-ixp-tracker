import logging
from datetime import datetime, timedelta
from typing import TypedDict, Any
from uuid import uuid4, UUID

from ixp_tracker.ixp_tracker_aggregates import is_ixp_active

from ixp_tracker.data_lookup import ASNGeoLookup
from ixp_tracker.event_store import (
    EventStore,
    AggregateNotFound,
)
import ixp_tracker.ixp_tracker_aggregates as ixpt
from ixp_tracker.models import IXPIdMap, ASNMap

logger = logging.getLogger("ixp_tracker")


class MemberImportData(TypedDict):
    asn: int
    created_date: datetime
    updated_date: datetime
    is_rs_peer: bool
    port_speed: int


class IXPTracker:
    def __init__(self, es: EventStore, geo_lookup: ASNGeoLookup):
        self.es = es
        self.geo_lookup = geo_lookup

    def import_ixp(
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
        exists = self.find_by_peeringdb_id(peeringdb_id)
        if exists:
            return self._update_ixp(
                exists,
                name,
                long_name,
                city,
                website,
                country_code,
                created,
                last_updated,
                last_active,
                org_id,
                manrs_participant,
                anchor_host,
                physical_locations,
            )
        active_status = False
        ixp = ixpt.IXP(id=uuid4())
        event = ixpt.IXPCreated(
            name,
            long_name,
            city,
            peeringdb_id,
            website,
            active_status,
            country_code,
            ixpt.stringify_date(created),
            ixpt.stringify_date(last_updated),
            ixpt.stringify_date(last_active),
            manrs_participant,
            anchor_host,
            org_id,
            physical_locations,
        )
        ixp = self.es.store(ixp, event)
        return ixp

    def _update_ixp(
        self,
        ixp: ixpt.IXP,
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
            updates["created"] = ixpt.stringify_date(created)
        if last_updated != ixp.last_updated:
            updates["last_updated"] = ixpt.stringify_date(last_updated)
        if org_id != ixp.org_id:
            updates["org_id"] = org_id
        if len(updates.keys()) > 0:
            event = ixpt.IXPUpdated(**updates)
            ixp = self.es.store(ixp, event)
        if ixp.manrs_participant != manrs_participant:
            manrs_update = ixpt.ManrsStatusChange(manrs_participant=manrs_participant)
            ixp = self.es.store(ixp, manrs_update)
        if ixp.anchor_host != anchor_host:
            anchor_host_event = ixpt.AnchorHostChange(anchor_host=anchor_host)
            ixp = self.es.store(ixp, anchor_host_event)
        if (
            ixp.physical_locations != physical_locations
            and physical_locations is not None
        ):
            locations_event = ixpt.PhysicalLocationChange(
                physical_locations=physical_locations
            )
            ixp = self.es.store(ixp, locations_event)
        active_event = ixpt.IXPActiveInPeeringDb(
            last_active=ixpt.stringify_date(last_active)
        )
        ixp = self.es.store(ixp, active_event)
        return ixp

    def import_asn(
        self,
        as_number: int,
        name: str,
        network_type: ixpt.NetworkType,
        peering_policy: ixpt.PeeringPolicy,
        peeringdb_id: int,
        country_code,
        is_routed: bool,
        customer_asns: list[int],
    ):
        entity = self.get_asn(as_number)
        if entity:
            updates: dict[str, Any] = {}
            if name != entity.name:
                updates["name"] = name
            if network_type != entity.network_type:
                updates["network_type"] = network_type.value
            if peering_policy != entity.peering_policy:
                updates["peering_policy"] = peering_policy.value
            if country_code != entity.country_code:
                updates["country_code"] = country_code
            if is_routed != entity.is_routed:
                updates["is_routed"] = is_routed
            if customer_asns != entity.customer_asns:
                updates["customer_asns"] = customer_asns
            if len(updates.keys()) > 0:
                update_event = ixpt.ASNUpdated(**updates)
                entity = self.es.store(entity, update_event)
            if peeringdb_id != entity.peeringdb_id:
                peering_id_event = ixpt.ASNPeeringDbIdChanged(peeringdb_id=peeringdb_id)
                entity = self.es.store(entity, peering_id_event)
        else:
            entity = ixpt.ASN(id=uuid4())
            event = ixpt.ASNCreated(
                as_number,
                name,
                network_type.value,
                peering_policy.value,
                peeringdb_id,
                country_code,
                is_routed,
                customer_asns,
            )
            entity = self.es.store(entity, event)
        return entity

    def import_members(
        self,
        ixp: ixpt.IXP,
        ixp_data: list[MemberImportData],
        processing_date: datetime,
    ) -> ixpt.IXP:
        existing_members = ixp.get_members(True)
        for member in ixp_data:
            as_entity = self.get_asn(member["asn"])
            if as_entity is None:
                logger.warning("Cannot find AS", extra={"asn": member["asn"]})
                continue
            existing_member = existing_members.get(member["asn"])
            member_registered_to_zz_and_has_left_already = (
                existing_member
                and existing_member.date_left is not None
                and as_zz_country_check(member["asn"], processing_date, self.geo_lookup)
            )
            if member_registered_to_zz_and_has_left_already:
                continue
            date_updated = ixpt.stringify_date(member["updated_date"])
            member_has_rejoined = (
                existing_member and existing_member.date_left is not None
            )
            if existing_member is None or member_has_rejoined:
                join_event = ixpt.IXPMemberJoined(
                    member["asn"],
                    ixpt.stringify_date(processing_date),
                    date_updated,
                    ixpt.stringify_date(processing_date),
                    member["is_rs_peer"],
                    member["port_speed"],
                )
                ixp = self.es.store(ixp, join_event)
            else:
                if member["port_speed"] != existing_member.port_speed:
                    update_event = ixpt.PortSpeedUpdated(
                        member["asn"], member["port_speed"], date_updated
                    )
                    ixp = self.es.store(ixp, update_event)
                if member["is_rs_peer"] != existing_member.is_rs_peer:
                    rs_peer_event = ixpt.RsPeeringStatusChange(
                        member["asn"], member["is_rs_peer"], date_updated
                    )
                    ixp = self.es.store(ixp, rs_peer_event)
                active_event = ixpt.IXPMemberActiveInPeeringDb(
                    member["asn"], ixpt.stringify_date(processing_date)
                )
                ixp = self.es.store(ixp, active_event)

        ixp = self.check_ixp_inactive(ixp, processing_date)
        self.es.save_snapshot(ixp)
        return ixp

    def check_ixp_inactive(self, ixp: ixpt.IXP, processing_date: datetime) -> ixpt.IXP:
        members = ixp.get_members()
        members_left = check_if_members_have_left(
            members, processing_date, self.geo_lookup
        )
        for member_left in members_left:
            left_event = ixpt.IXPMemberLeft(
                member_left[0], ixpt.stringify_date(member_left[1])
            )
            ixp = self.es.store(ixp, left_event)
        member_asns = list(ixp.get_members().keys())
        if ixp.active_status is False and is_ixp_active(member_asns):
            active_event = ixpt.IXPBecameActive()
            ixp = self.es.store(ixp, active_event)
        elif ixp.active_status is True and not is_ixp_active(member_asns):
            inactive_event = ixpt.IXPBecameInactive()
            ixp = self.es.store(ixp, inactive_event)
        return ixp

    def find_by_peeringdb_id(self, peeringdb_id: int) -> ixpt.IXP | None:
        try:
            id_map = IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
            return self.es.get_aggregate(id_map.aggregate_id, ixpt.IXP)
        except (IXPIdMap.DoesNotExist, AggregateNotFound):
            return None

    def find_isoc_id(self, aggregate_id: UUID) -> int | None:
        try:
            id_map = IXPIdMap.objects.get(aggregate_id=aggregate_id)
            return id_map.id
        except IXPIdMap.DoesNotExist:
            return None

    def get_all_ixps(self, as_at: datetime | None = None):
        return self.es.get_all(ixpt.IXP, as_at)

    def get_all_asns(self):
        return self.es.get_all(ixpt.ASN)

    def get_asn(self, asn) -> ixpt.ASN | None:
        try:
            asn_map = ASNMap.objects.get(asn=asn)
            return self.es.get_aggregate(asn_map.aggregate_id, ixpt.ASN)
        except ASNMap.DoesNotExist:
            return None

    def time_travel(self, date_in_past: datetime):
        self.es.time_travel(date_in_past)


def check_if_members_have_left(
    members: dict[int, ixpt.IXPMemberDetails],
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
        if member.date_left is None and as_zz_country_check(
            member_asn, processing_date, geo_lookup
        ):
            end_of_last_month_active = member.last_active.replace(day=1) - timedelta(
                days=1
            )
            members_left.append((member_asn, end_of_last_month_active))
    return members_left


def as_zz_country_check(asn: int, as_at: datetime, geo_lookup: ASNGeoLookup) -> bool:
    # AS112 is a special case, see https://www.as112.net). It's marked as registered to country ZZ in NRO so we ignore it here
    if asn == 112:
        return False
    country = geo_lookup.get_iso2_country(asn, as_at)
    status = geo_lookup.get_status(asn, as_at)
    if country != "ZZ":
        return False
    if status == "assigned":
        logger.warning(
            "AS registered to ZZ and marked as assigned",
            extra={"asn": asn, "date": as_at},
        )
        return False
    return True
