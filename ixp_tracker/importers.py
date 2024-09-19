import ast
import json
from json.decoder import JSONDecodeError
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Protocol

import requests
import dateutil.parser
from django_countries import countries

from ixp_tracker.conf import IXP_TRACKER_PEERING_DB_KEY, IXP_TRACKER_PEERING_DB_URL, DATA_ARCHIVE_URL
from ixp_tracker import models
from ixp_tracker.models import IXPMembershipRecord

logger = logging.getLogger("ixp_tracker")


class ASNGeoLookup(Protocol):

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass

    def get_asns_for_country(self, country: str, as_at: datetime) -> List[int]:
        pass


def import_data(
        geo_lookup: ASNGeoLookup,
        reset: bool = False,
        processing_date: datetime = None,
        page_limit: int = 200
):
    if processing_date is None:
        processing_date = datetime.utcnow().replace(tzinfo=timezone.utc)
        import_ixps(processing_date)
        logger.debug("Imported IXPs")
        import_asns(geo_lookup, reset, page_limit)
        logger.debug("Imported ASNs")
        import_members(processing_date, geo_lookup)
        logger.debug("Imported members")
    else:
        processing_date = processing_date.replace(day=1)
        processing_month = processing_date.month
        found = False
        while processing_date.month == processing_month and not found:
            url = DATA_ARCHIVE_URL.format(year=processing_date.year, month=processing_date.month, day=processing_date.day)
            data = requests.get(url)
            if data.status_code == 200:
                found = True
            else:
                processing_date = processing_date + timedelta(days=1)
        if not found:
            logger.warning("Cannot find backfill data", extra={"backfill_date": processing_date})
            return
        backfill_raw = data.text
        try:
            backfill_data = json.loads(backfill_raw)
        except JSONDecodeError:
            # It seems some of the Peering dumps use single quotes so try and load using ast in this case
            backfill_data = ast.literal_eval(backfill_raw)
        ixp_data = backfill_data.get("ix", {"data": []}).get("data", [])
        process_ixp_data(processing_date)(ixp_data)
        asn_data = backfill_data.get("net", {"data": []}).get("data", [])
        process_asn_data(geo_lookup)(asn_data)
        member_data = backfill_data.get("netixlan", {"data": []}).get("data", [])
        process_member_data(processing_date, geo_lookup)(member_data)


def get_data(endpoint: str, processor: Callable, limit: int = 0, last_updated: datetime = None) -> bool:
    url = f"{IXP_TRACKER_PEERING_DB_URL}{endpoint}"
    query_params = {}
    if last_updated is not None:
        query_params["updated__gte"] = last_updated.strftime("%Y-%m-%d")
    if limit > 0:
        query_params["limit"] = limit
        query_params["skip"] = 0
    finished = False
    while finished is not True:
        finished = True
        data = requests.get(url, headers={"Authorization": f"Api-Key {IXP_TRACKER_PEERING_DB_KEY}"}, params=query_params)
        if data.status_code >= 300:
            logger.warning("Cannot retrieve data", extra={"status": data.status_code})
            return False
        try:
            data = data.json().get("data", [])
            processor(data)
            if limit > 0 and len(data) > 0:
                query_params["skip"] = query_params["skip"] + limit
                finished = False
        except JSONDecodeError:
            logger.warning("Cannot decode json data")
            return False
    return True


def import_ixps(processing_date) -> bool:
    return get_data("/ix", process_ixp_data(processing_date))


def process_ixp_data(processing_date: datetime):
    def do_process_ixp_data(all_ixp_data):
        for ixp_data in all_ixp_data:
            country_data = countries.alpha2(ixp_data["country"])
            if len(country_data) == 0:
                logger.warning("Skipping IXP import as country code not found", extra={"country": ixp_data["country"], "id": ixp_data["id"]})
                continue
            try:
                models.IXP.objects.update_or_create(
                    peeringdb_id=ixp_data["id"],
                    defaults={
                        "name": ixp_data["name"],
                        "long_name": ixp_data["name_long"],
                        "city": ixp_data["city"],
                        "website": ixp_data["website"],
                        "active_status": True,
                        "country_code": ixp_data["country"],
                        "created": ixp_data["created"],
                        "last_updated": ixp_data["updated"],
                        "last_active": processing_date,
                    }
                )
                logger.debug("Creating new IXP record", extra={"id": ixp_data["id"]})
            except Exception as e:
                logger.warning("Cannot import IXP data", extra={"error": str(e)})
    return do_process_ixp_data


def import_asns(geo_lookup: ASNGeoLookup, reset: bool = False, page_limit: int = 200) -> bool:
    logger.debug("Fetching ASN data")
    updated_since = None
    if not reset:
        last_updated = models.ASN.objects.all().order_by("-last_updated").first()
        if last_updated:
            updated_since = last_updated.last_updated
    return get_data("/net", process_asn_data(geo_lookup), limit=page_limit, last_updated=updated_since)


def process_asn_data(geo_lookup):
    def process_asn_paged_data(all_asn_data):
        for asn_data in all_asn_data:
            try:
                asn = int(asn_data["asn"])
                last_updated = dateutil.parser.isoparse(asn_data["updated"])
                models.ASN.objects.update_or_create(
                    peeringdb_id=asn_data["id"],
                    defaults={
                        "name": asn_data["name"],
                        "number": asn,
                        "network_type": asn_data["info_type"],
                        "registration_country_code": geo_lookup.get_iso2_country(asn, last_updated),
                        "created": asn_data["created"],
                        "last_updated": last_updated,
                    }
                )
            except Exception as e:
                logger.warning("Cannot import ASN data", extra={"error": str(e)})
        return True
    return process_asn_paged_data


def import_members(processing_date: datetime, geo_lookup: ASNGeoLookup) -> bool:
    logger.debug("Fetching IXP member data")
    return get_data("/netixlan", process_member_data(processing_date, geo_lookup))


def process_member_data(processing_date: datetime, geo_lookup: ASNGeoLookup):

    def do_process_member_data(all_member_data):
        all_member_data = dedupe_member_data(all_member_data)
        for member_data in all_member_data:
            log_data = {"asn": member_data["asn"], "ixp": member_data["ix_id"]}
            try:
                ixp = models.IXP.objects.get(peeringdb_id=member_data["ix_id"])
            except models.IXP.DoesNotExist:
                logger.warning("Cannot find IXP")
                continue
            try:
                asn = models.ASN.objects.get(number=member_data["asn"])
            except models.ASN.DoesNotExist:
                logger.warning("Cannot find ASN")
                continue
            member, created = models.IXPMember.objects.update_or_create(
                ixp=ixp,
                asn=asn,
                defaults={
                    "last_updated": member_data["updated"],
                    "last_active": processing_date,
                }
            )
            created_date = dateutil.parser.isoparse(member_data["created"]).date()
            membership = models.IXPMembershipRecord.objects.filter(member=member).order_by("-start_date").first()
            if created or membership is None:
                membership = IXPMembershipRecord(
                    member=member,
                    start_date=created_date,
                    is_rs_peer=member_data["is_rs_peer"],
                    speed=member_data["speed"]
                )
                membership.save()
                logger.debug("Created new membership for new member", extra=log_data)
            else:
                if membership.end_date is None:
                    # Membership is current so just update the details if needed
                    membership.is_rs_peer = member_data["is_rs_peer"]
                    membership.speed = member_data["speed"]
                else:
                    if created_date == membership.start_date:
                        # Avoid re-adding a member for the same start_date
                        continue
                    if membership.end_date > created_date:
                        logger.warning("We might have overlapping memberships", extra=log_data)
                    # Most recent membership has ended so create a new membership record
                    membership = IXPMembershipRecord(
                        member=member,
                        start_date=created_date,
                        is_rs_peer=member_data["is_rs_peer"],
                        speed=member_data["speed"]
                    )
                    logger.debug("Created new membership as previous one ended", extra=log_data)
                membership.save()

            logger.debug("Imported IXP member record", extra=log_data)
        start_of_month = processing_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        inactive = models.IXPMember.objects.filter(last_active__lt=start_of_month).all()
        for member in inactive:
            latest_membership = models.IXPMembershipRecord.objects.filter(member=member).order_by("-start_date").first()
            if latest_membership.end_date is not None:
                continue
            start_of_next_of_month = (member.last_active.replace(day=1) + timedelta(days=33)).replace(day=1)
            end_of_month = start_of_next_of_month - timedelta(days=1)
            latest_membership.end_date = end_of_month
            latest_membership.save()
            logger.debug("Member flagged as left due to inactivity", extra={"member": member.asn.number})
        candidates = models.IXPMember.objects.filter(asn__registration_country_code="ZZ").all()
        for candidate in candidates:
            latest_membership = models.IXPMembershipRecord.objects.filter(member=candidate).order_by("-start_date").first()
            if latest_membership.end_date is not None:
                continue
            if geo_lookup.get_status(candidate.asn.number, processing_date) != "assigned":
                end_of_last_month_active = (candidate.last_active.replace(day=1) - timedelta(days=1))
                if end_of_last_month_active.date() < latest_membership.start_date:
                    # It can happen that a member is immediately marked as left as the AS is not registered to a country
                    # In this case make sure the date we are using for the membership end date is not before the start_date
                    end_of_last_month_active = latest_membership.start_date
                latest_membership.end_date = end_of_last_month_active
                latest_membership.save()
                logger.debug("Member flagged as left due to unassigned ASN", extra={"member": candidate.asn.number})
        logger.info("Fixing members finished")
    return do_process_member_data


def dedupe_member_data(raw_members_data):
    deduped_data = {}
    for raw_member in raw_members_data:
        member_key = str(raw_member["ix_id"]) + "-" + str(raw_member["asn"])
        if deduped_data.get(member_key) is None:
            deduped_data[member_key] = dict(raw_member)
        else:
            deduped_data[member_key]["is_rs_peer"] = deduped_data[member_key]["is_rs_peer"] or raw_member["is_rs_peer"]
            deduped_data[member_key]["speed"] += raw_member["speed"]
    return list(deduped_data.values())
