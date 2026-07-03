import json
import logging
from datetime import datetime
from json import JSONDecodeError
from typing import TypedDict, Any

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from ixp_tracker.conf import (
    IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH,
    IXP_TRACKER_PEERING_DB_URL,
)

logger = logging.getLogger("ixp_tracker")


class PeeringDbDataError(Exception):
    pass


class PeeringDbData(TypedDict):
    data: list[dict]


class AllPeeringDbData(TypedDict):
    as_set: PeeringDbData
    campus: PeeringDbData
    carrier: PeeringDbData
    carrierfac: PeeringDbData
    fac: PeeringDbData
    ix: PeeringDbData
    ixfac: PeeringDbData
    ixlan: PeeringDbData
    ixpfx: PeeringDbData
    net: PeeringDbData
    netfac: PeeringDbData
    netixlan: PeeringDbData
    org: PeeringDbData
    poc: PeeringDbData


def get_data(
    endpoint: str,
    limit: int = 0,
) -> list[dict]:
    url = f"{IXP_TRACKER_PEERING_DB_URL}{endpoint}"
    session = Session()
    retries = Retry(
        total=4,
        backoff_factor=0.5,
        status_forcelist=[
            413,
            429,
            500,
            502,
            503,
            504,
        ],  # retry if we receive one of these status codes
        allowed_methods={"GET"},
        raise_on_redirect=False,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    query_params: dict[str, Any] = {}
    if limit > 0:
        query_params["limit"] = limit
        query_params["skip"] = 0
    finished = False
    all_data = []
    while not finished:
        finished = True
        data = session.get(
            url,
            params=query_params,
        )
        if data.status_code >= 300:
            # How do we handle errors here? Perhaps we need retries? Or do we bail if there's a single error?
            logger.warning("Cannot retrieve data", extra={"status": data.status_code})
            raise PeeringDbDataError
        try:
            data = data.json().get("data", [])
            all_data += data
            if limit > 0 and len(data) > 0:
                query_params["skip"] = query_params["skip"] + limit
                finished = False
        except JSONDecodeError as e:
            # How do we handle errors here? Perhaps we need retries? Or do we bail if there's a single error?
            logger.warning("Cannot decode json data", extra={"error": str(e)})
            raise PeeringDbDataError
    return all_data


def gather_data() -> AllPeeringDbData:
    poc_data = [p for p in get_data("/poc") if p.get("visible") == "Public"]
    return {
        "as_set": {"data": get_data("/as_set")},
        "campus": {"data": get_data("/campus")},
        "carrier": {"data": get_data("/carrier")},
        "carrierfac": {"data": get_data("/carrierfac")},
        "fac": {"data": get_data("/fac")},
        "ix": {"data": get_data("/ix")},
        "ixfac": {"data": get_data("/ixfac")},
        "ixlan": {"data": get_data("/ixlan")},
        "ixpfx": {"data": get_data("/ixpfx")},
        "net": {"data": get_data("/net")},
        "netfac": {"data": get_data("/netfac")},
        "netixlan": {"data": get_data("/netixlan")},
        "org": {"data": get_data("/org")},
        "poc": {"data": poc_data},
    }


def save_data(all_data: AllPeeringDbData, processing_date: datetime):
    file_name = f"{IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH}/{processing_date.year}{processing_date.month:02}{processing_date.day:02}.peeringdb_2_dump.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
