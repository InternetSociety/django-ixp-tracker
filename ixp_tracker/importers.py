import logging
from datetime import datetime
from typing import Protocol

import requests
import dateutil.parser
from django.conf import settings
from requests.exceptions import JSONDecodeError

from ixp_tracker import models

logger = logging.getLogger("ixp_tracker")


class ASNGeoLookup(Protocol):

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass


def import_ixps() -> bool:
    reporting_date = datetime.utcnow()
    logger.debug("Fetching IXP data")
    base_url = settings.__getattr__("IXP_TRACKER_PEERING_DB_URL") or "https://www.peeringdb.com/api"
    url = f"{base_url}/ix"
    api_key = settings.__getattr__("IXP_TRACKER_PEERING_DB_KEY")
    data = requests.get(url, headers={"Authorization": f"Api-Key {api_key}"})
    if data.status_code >= 300:
        logger.warning("Cannot retrieve IXP data", extra={"status": data.status_code})
        return False
    try:
        all_ixp_data = data.json().get("data", [])
    except JSONDecodeError:
        logger.warning("Cannot decode json data")
        return False

    for ixp_data in all_ixp_data:
        models.IXP.objects.update_or_create(
            peeringdb_id=ixp_data["id"],
            defaults={
                "name": ixp_data["name"],
                "long_name": ixp_data["name_long"],
                "city": ixp_data["city"],
                "website": ixp_data["website"],
                "active_status": True,
                "country": ixp_data["country"],
                "created": ixp_data["created"],
                "last_updated": ixp_data["updated"],
                "last_active": reporting_date,
            }
        )
        logger.debug("Creating new IXP record", extra={"id": ixp_data["id"]})
    return True


def import_asns(geo_lookup: ASNGeoLookup, reset: bool = False, page_limit: int = 200) -> bool:
    logger.debug("Fetching ASN data")
    base_url = settings.__getattr__("IXP_TRACKER_PEERING_DB_URL") or "https://www.peeringdb.com/api"
    url = f"{base_url}/net"
    query_params = {"limit": page_limit, "skip": 0}
    if not reset:
        last_updated = models.ASN.objects.all().order_by("-last_updated").first()
        if last_updated:
            query_params["updated__gte"] = "2024-06-01"
    api_key = settings.__getattr__("IXP_TRACKER_PEERING_DB_KEY")
    done = False
    while done is not True:
        done = True
        data = requests.get(url, params=query_params, headers={"Authorization": f"Api-Key {api_key}"})
        if data.status_code >= 300:
            logger.warning("Cannot retrieve ASN data", extra={"status": data.status_code})
            return False
        try:
            all_asn_data = data.json().get("data", [])
        except JSONDecodeError:
            logger.warning("Cannot decode json data")
            return False

        for asn_data in all_asn_data:
            done = False
            asn = int(asn_data["asn"])
            last_updated = dateutil.parser.isoparse(asn_data["updated"])
            models.ASN.objects.update_or_create(
                peeringdb_id=asn_data["id"],
                defaults={
                    "name": asn_data["name"],
                    "number": asn,
                    "network_type": asn_data["info_type"],
                    "registration_country": geo_lookup.get_iso2_country(asn, last_updated),
                    "created": asn_data["created"],
                    "last_updated": last_updated,
                }
            )
        query_params["skip"] = query_params["skip"] + page_limit
    return True
