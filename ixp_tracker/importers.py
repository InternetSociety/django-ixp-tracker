import ast
import json
import logging
from datetime import datetime, timedelta, timezone
from glob import glob
from json.decoder import JSONDecodeError

import dateutil.parser
import requests
from django.db.models import Q
from django_countries import countries

from ixp_tracker import models
from ixp_tracker.conf import (
    DATA_ARCHIVE_URL,
    IXP_TRACKER_ENABLE_EVENT_SOURCING,
    IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH,
)
from ixp_tracker.data_lookup import AdditionalDataSources, ASNGeoLookup
from ixp_tracker.event_store import DjangoEventStore, EventStore
from ixp_tracker.gather_data import gather_data, save_data
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    MemberImportData,
)
from ixp_tracker.ixp_tracker_aggregates import (
    IXP_TRACKER_EVENT_MAP,
    NetworkType,
    PeeringPolicy,
    is_ixp_active,
    NROStatus,
)
from ixp_tracker.ixp_tracker_projections import (
    ASNList,
    IXPIdMapProjection,
    IXPsLastUpdatedProjection,
)

logger = logging.getLogger("ixp_tracker")
PEERING_DB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def import_data(
    additional_data: AdditionalDataSources,
    processing_date: datetime | None = None,
    disable_event_sourcing: bool = False,
):
    if processing_date is None:
        processing_date = datetime.now(timezone.utc)
        try:
            all_pdb_data = gather_data()
            save_data(all_pdb_data, processing_date)
        except Exception as e:
            logger.error(
                "Cannot download latest PeeringDB data", extra={"error": str(e)}
            )
            return
    else:
        processing_date = processing_date.replace(day=1)
        processing_month = processing_date.month
        found = False
        backfill_raw = None
        if IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH is not None:
            archive_search_path = f"{IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH}/{processing_date.year}{processing_date.month:02}*"
            logger.debug(
                "Searching for archive file locally",
                extra={"search_path": archive_search_path},
            )
            possible_files = glob(archive_search_path)
            if len(possible_files) > 0:
                possible_files.sort()
                archive_file = possible_files[0]
                file_date = archive_file.replace(
                    IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH + "/", ""
                ).split(".")[0]
                processing_date = datetime.strptime(file_date, "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
                with open(archive_file) as f:
                    backfill_raw = f.read()
                    found = True
                    logger.debug(
                        "Found archive file locally",
                        extra={
                            "archive_file": archive_file,
                            "processing_date": processing_date,
                        },
                    )
        while processing_date.month == processing_month and not found:
            url = DATA_ARCHIVE_URL.format(
                year=processing_date.year,
                month=processing_date.month,
                day=processing_date.day,
            )
            data = requests.get(url)
            if data.status_code == 200:
                found = True
                backfill_raw = data.text
                logger.debug(
                    "Retrieved archive file from CAIDA",
                    extra={"processing_date": processing_date},
                )
            else:
                processing_date = processing_date + timedelta(days=1)
        if not found or not backfill_raw:
            logger.warning(
                "Cannot find backfill data", extra={"backfill_date": processing_date}
            )
            return
        try:
            all_pdb_data = json.loads(backfill_raw)
        except JSONDecodeError:
            # It seems some of the Peering dumps use single quotes so try and load using ast in this case
            all_pdb_data = ast.literal_eval(backfill_raw)
    es_app = build_app(processing_date, disable_event_sourcing)
    ixp_data = all_pdb_data.get("ix", {"data": []}).get("data", [])
    process_ixp_data(ixp_data, processing_date, additional_data, es_app)
    asn_data = all_pdb_data.get("net", {"data": []}).get("data", [])
    # This is an optimisation to improve import performance. Peering DB list of networks contains about 2x the number of networks in the member list
    # So, fo now, we choose only to import the ASN data referenced in the member data
    member_data = all_pdb_data.get("netixlan", {"data": []}).get("data", [])
    member_asns = set([int(m["asn"]) for m in member_data])
    filtered_asn_data = [a for a in asn_data if a["asn"] in member_asns]
    process_asn_data(filtered_asn_data, processing_date, additional_data, es_app)
    process_member_data(member_data, processing_date, additional_data, es_app)
    toggle_ixp_active_status(processing_date, es_app)
    logger.debug("Toggled IXPs active status")


def build_app(
    import_date: datetime | None = None,
    disable_event_sourcing: bool = False,
) -> IXPTracker | None:
    if not IXP_TRACKER_ENABLE_EVENT_SOURCING or disable_event_sourcing:
        return None
    es = EventStore(IXP_TRACKER_EVENT_MAP, DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    es.add_listener(IXPsLastUpdatedProjection())
    app = IXPTracker(es)
    if import_date:
        # We always set the time travel so the monthly stats can run safely for the first of each month,
        # and we set the time elements to zero to ensure we always get all events for that date
        app.time_travel(import_date.replace(hour=0, minute=0, second=0, microsecond=0))
    return app


def process_ixp_data(
    all_ixp_data,
    processing_date: datetime,
    data_lookup: AdditionalDataSources,
    event_sourcing_app: IXPTracker | None = None,
):
    manrs_participants = data_lookup.get_manrs_participants(processing_date)
    anchor_hosts = data_lookup.get_atlas_anchor_hosts(processing_date)
    ixps_added = 0
    ixps_updated = 0
    for ixp_data in all_ixp_data:
        country_data = countries.alpha2(ixp_data["country"])
        if len(country_data) == 0:
            logger.warning(
                "Skipping IXP import as country code not found",
                extra={"country": ixp_data["country"], "id": ixp_data["id"]},
            )
            continue
        try:
            if event_sourcing_app:
                peeringdb_id = int(ixp_data["id"])
                date_created = datetime.strptime(
                    ixp_data["created"], PEERING_DB_DATE_FORMAT
                ).replace(tzinfo=timezone.utc)
                last_updated = datetime.strptime(
                    ixp_data["updated"], PEERING_DB_DATE_FORMAT
                ).replace(tzinfo=timezone.utc)
                physical_locations = (
                    int(ixp_data["fac_count"])
                    if ixp_data.get("fac_count") is not None
                    else None
                )
                _ixp = event_sourcing_app.import_ixp(
                    ixp_data["name"],
                    ixp_data["name_long"],
                    ixp_data["city"],
                    peeringdb_id,
                    ixp_data["website"],
                    ixp_data["country"],
                    date_created,
                    last_updated,
                    processing_date,
                    ixp_data["id"] in manrs_participants,
                    ixp_data["id"] in anchor_hosts,
                    int(ixp_data["org_id"]),
                    physical_locations,
                )
                logger.debug(
                    "Importing IXP record from Peering Db",
                    extra={"id": ixp_data["id"]},
                )
                ixps_updated += 1

            else:
                _, created = models.IXP.objects.update_or_create(
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
                        "manrs_participant": ixp_data["id"] in manrs_participants,
                        "anchor_host": ixp_data["id"] in anchor_hosts,
                        "org_id": ixp_data["org_id"],
                        "physical_locations": ixp_data["fac_count"],
                    },
                )
                logger.debug(
                    "Importing IXP record from Peering Db",
                    extra={"id": ixp_data["id"]},
                )
                if created:
                    ixps_added += 1
                else:
                    ixps_updated += 1
        except Exception as e:
            logger.warning("Cannot import IXP data", extra={"error": str(e)})
    logger.info(
        "Processed IXP data",
        extra={"added": ixps_added, "updated": ixps_updated},
    )


def process_asn_data(
    all_asn_data,
    processing_date: datetime,
    geo_lookup: AdditionalDataSources,
    event_sourcing_app: IXPTracker | None = None,
):
    for asn_data in all_asn_data:
        try:
            asn = int(asn_data["asn"])
            last_updated = dateutil.parser.isoparse(asn_data["updated"])
            if event_sourcing_app:
                country_code = geo_lookup.get_iso2_country(asn, processing_date)
                routed_asns = geo_lookup.get_routed_asns_for_country(
                    country_code, processing_date
                )
                try:
                    nro_status = NROStatus(geo_lookup.get_status(asn, processing_date))
                except ValueError:
                    nro_status = NROStatus.UNKNOWN
                try:
                    network_type = NetworkType(asn_data["info_type"])
                except ValueError:
                    network_type = NetworkType.UNKNOWN
                try:
                    peering_policy = PeeringPolicy(asn_data["policy_general"])
                except ValueError:
                    peering_policy = PeeringPolicy.UNKNOWN
                event_sourcing_app.import_asn(
                    asn,
                    asn_data["name"],
                    network_type,
                    peering_policy,
                    asn_data["id"],
                    country_code,
                    nro_status,
                    asn in routed_asns,
                    geo_lookup.get_customer_asns([asn], processing_date),
                )
            else:
                country_code = geo_lookup.get_iso2_country(asn, last_updated)
                models.ASN.objects.update_or_create(
                    peeringdb_id=asn_data["id"],
                    defaults={
                        "name": asn_data["name"],
                        "number": asn,
                        "network_type": asn_data["info_type"],
                        "peering_policy": asn_data["policy_general"],
                        "registration_country_code": country_code,
                        "created": asn_data["created"],
                        "last_updated": last_updated,
                    },
                )
        except Exception as e:
            logger.warning("Cannot import ASN data", extra={"error": str(e)})
    return True


def process_member_data(
    all_member_data,
    processing_date: datetime,
    geo_lookup: ASNGeoLookup,
    event_sourcing_app: IXPTracker | None = None,
):
    all_member_data = dedupe_member_data(all_member_data)
    if event_sourcing_app:
        ixp_member_data: dict[int, list[MemberImportData]] = {}
        for member_data in all_member_data:
            asn = int(member_data["asn"])
            created_date = datetime.strptime(
                member_data["created"], PEERING_DB_DATE_FORMAT
            ).replace(tzinfo=timezone.utc)
            updated_date = datetime.strptime(
                member_data["updated"], PEERING_DB_DATE_FORMAT
            ).replace(tzinfo=timezone.utc)
            is_rs_peer = bool(member_data["is_rs_peer"])
            port_speed = int(member_data["speed"])
            ix_id = int(member_data["ix_id"])
            import_data: MemberImportData = {
                "asn": asn,
                "created_date": created_date,
                "updated_date": updated_date,
                "is_rs_peer": is_rs_peer,
                "port_speed": port_speed,
            }
            seen = ixp_member_data.get(ix_id)
            if not seen:
                ixp_member_data[ix_id] = [import_data]
            else:
                ixp_member_data[ix_id] += [import_data]
        ixps = event_sourcing_app.get_all_ixps()
        updated = []
        for peeringdb_id in ixp_member_data:
            try:
                log_data = {"ixp": peeringdb_id}
                logger.debug("Importing IXP members", extra=log_data)
                ixp = next(
                    (ixp for ixp in ixps if ixp.peeringdb_id == peeringdb_id), None
                )
                if ixp is None:
                    logger.warning("Cannot find IXP", extra=log_data)
                    continue
                ixp = event_sourcing_app.import_members(
                    ixp, ixp_member_data[peeringdb_id], processing_date
                )
                log_data["member_count"] = len(ixp.get_members(True))
                updated.append(ixp.id)
                logger.debug("Imported IXP members", extra=log_data)
            except Exception as e:
                logger.warning(
                    "Cannot import IXP members",
                    extra={"ixp": peeringdb_id, "error": str(e)},
                )
        for ixp in ixps:
            if ixp.id in updated:
                continue
            logger.debug(
                "Marking IXP members inactive", extra={"ixp_id": ixp.peeringdb_id}
            )
            event_sourcing_app.check_ixp_inactive(ixp, processing_date)
    else:
        for member_data in all_member_data:
            log_data = {"asn": member_data["asn"], "ixp": member_data["ix_id"]}
            try:
                peeringdb_id = models.IXP.objects.get(peeringdb_id=member_data["ix_id"])
            except models.IXP.DoesNotExist:
                logger.warning("Cannot find IXP")
                continue
            try:
                asn = models.ASN.objects.get(number=member_data["asn"])
            except models.ASN.DoesNotExist:
                logger.warning("Cannot find ASN")
                continue
            member, created = models.IXPMember.objects.update_or_create(
                ixp=peeringdb_id,
                asn=asn,
                defaults={
                    "last_updated": member_data["updated"],
                    "last_active": processing_date,
                },
            )
            created_date = dateutil.parser.isoparse(member_data["created"]).date()
            membership = (
                models.IXPMembershipRecord.objects.filter(member=member)
                .order_by("-start_date")
                .first()
            )
            if created or membership is None:
                membership = models.IXPMembershipRecord(
                    member=member,
                    start_date=created_date,
                    is_rs_peer=member_data["is_rs_peer"],
                    speed=member_data["speed"],
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
                        logger.debug("Extending membership", extra=log_data)
                        membership.end_date = None
                    else:
                        # Most recent membership has ended so create a new membership record
                        membership = models.IXPMembershipRecord(
                            member=member,
                            start_date=created_date,
                            is_rs_peer=member_data["is_rs_peer"],
                            speed=member_data["speed"],
                        )
                        logger.debug(
                            "Created new membership as previous one ended",
                            extra=log_data,
                        )
                membership.save()

            logger.debug("Imported IXP member record", extra=log_data)
        start_of_month = processing_date.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        inactive = models.IXPMember.objects.filter(last_active__lt=start_of_month).all()
        for member in inactive:
            latest_membership = (
                models.IXPMembershipRecord.objects.filter(member=member)
                .order_by("-start_date")
                .first()
            )
            if latest_membership.end_date is not None:
                continue
            start_of_next_of_month = (
                member.last_active.replace(day=1) + timedelta(days=33)
            ).replace(day=1)
            end_of_month = start_of_next_of_month - timedelta(days=1)
            latest_membership.end_date = end_of_month
            latest_membership.save()
            logger.debug(
                "Member flagged as left due to inactivity",
                extra={"member": member.asn.number},
            )
        candidates = models.IXPMember.objects.filter(
            asn__registration_country_code="ZZ"
        ).all()
        for candidate in candidates:
            latest_membership = (
                models.IXPMembershipRecord.objects.filter(member=candidate)
                .order_by("-start_date")
                .first()
            )
            if latest_membership.end_date is not None:
                continue
            if (
                geo_lookup.get_status(candidate.asn.number, processing_date)
                != "assigned"
            ):
                end_of_last_month_active = candidate.last_active.replace(
                    day=1
                ) - timedelta(days=1)
                if end_of_last_month_active.date() < latest_membership.start_date:
                    # It can happen that a member is immediately marked as left as the AS is not registered to a country
                    # In this case make sure the date we are using for the membership end date is not before the start_date
                    end_of_last_month_active = latest_membership.start_date
                latest_membership.end_date = end_of_last_month_active
                latest_membership.save()
                logger.debug(
                    "Member flagged as left due to unassigned ASN",
                    extra={"member": candidate.asn.number},
                )
    logger.info("Fixing members finished")


def dedupe_member_data(raw_members_data):
    deduped_data = {}
    for raw_member in raw_members_data:
        member_key = str(raw_member["ix_id"]) + "-" + str(raw_member["asn"])
        if deduped_data.get(member_key) is None:
            deduped_data[member_key] = dict(raw_member)
        else:
            deduped_data[member_key]["is_rs_peer"] = (
                deduped_data[member_key]["is_rs_peer"] or raw_member["is_rs_peer"]
            )
            deduped_data[member_key]["speed"] += raw_member["speed"]
    return list(deduped_data.values())


def toggle_ixp_active_status(
    processing_date: datetime, event_sourcing_app: IXPTracker | None = None
):
    if event_sourcing_app:
        pass
    else:
        for ixp in models.IXP.objects.all():
            active_members = models.IXPMembershipRecord.objects.filter(
                member__in=ixp.ixpmember_set.all()  # type: ignore
            ).filter(Q(end_date__isnull=True) | Q(end_date__gte=processing_date))
            # Note that `last_active` is the date we last saw the IXP in the source data and is used to track deletions
            # We update `last_updated` here when we toggle the active status as we use that to signify our IXP record has been changed
            # even though usually `last_updated` is taken from the source data field of the same name
            new_active_status = is_ixp_active(list(active_members))
            if ixp.active_status != new_active_status:
                ixp.active_status = new_active_status
                ixp.last_updated = processing_date
                ixp.save()
                logger.debug(
                    "Toggle IXP active status", extra={"ixp": ixp.peeringdb_id}
                )
    return
