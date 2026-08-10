from datetime import datetime, timedelta

from ixp_tracker.data_lookup import ASNGeoLookup
from ixp_tracker.ixp_tracker import as_zz_country_check
from ixp_tracker.ixp_tracker_aggregates import NROStatus


def check_org_networks(
    ixs: list[dict], networks: list[dict], asn_lookup: ASNGeoLookup, as_at: datetime
) -> dict[int, bool | None]:
    """
    We need to return None if there is no data as there's no requirement for an org to have a network in PDB.
    We may need this distinction later in the process when deciding to re-activate an IXP that has previously beem
    de-activated due to this logic. Lack of data is probably not a strong enough signal to activate or de-activate an IXP.
    """
    ixp_checks: dict[int, bool | None] = {}
    last_month = (as_at.replace(day=1) - timedelta(days=1)).replace(day=1)
    for ix in ixs:
        org_id = ix.get("org_id", 0)
        if org_id == 0:
            ixp_checks[ix["id"]] = None
            continue
        org_networks = [n["asn"] for n in networks if n.get("org_id", 0) == org_id]
        if len(org_networks) == 0:
            ixp_checks[ix["id"]] = None
            continue
        if any(
            as_zz_country_check(
                n,
                asn_lookup.get_iso2_country(n, as_at),
                NROStatus(asn_lookup.get_status(n, as_at)),
            )
            for n in org_networks
        ):
            ixp_checks[ix["id"]] = True
            continue
        if any(
            as_zz_country_check(
                n,
                asn_lookup.get_iso2_country(n, last_month),
                NROStatus(asn_lookup.get_status(n, last_month)),
            )
            for n in org_networks
        ):
            ixp_checks[ix["id"]] = True
            continue
        ixp_checks[ix["id"]] = False
    return ixp_checks
