import logging
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from django_countries import countries

from ixp_tracker.importers import AdditionalDataSources, build_app
from ixp_tracker.ixp_tracker import IXPTracker
from ixp_tracker.models import (
    StatsPerCountry,
    StatsPerIXP,
)

logger = logging.getLogger("ixp_tracker")


class CountryStats(TypedDict):
    ixp_count: int
    all_asns: list[int] | None
    routed_asns: list[int] | None
    member_asns: set[int]
    member_and_customer_asns: set[int]
    total_capacity: int


def generate_stats(
    lookup: AdditionalDataSources,
    stats_date: datetime | None = None,
):
    stats_date = stats_date or datetime.now(timezone.utc)
    es_app = build_app()
    do_generate_stats(lookup, es_app, stats_date)


def do_generate_stats(
    lookup: AdditionalDataSources,
    es_app: IXPTracker,
    stats_date: datetime | None = None,
):
    stats_date = stats_date or datetime.now(timezone.utc)
    stats_date = stats_date.replace(day=1)
    date_now = datetime.now(timezone.utc)
    date_12_months_ago = stats_date.replace(year=(stats_date.year - 1))
    date_last_month = (stats_date - timedelta(days=1)).replace(day=1)
    all_stats_per_country: dict[str, CountryStats] = {}
    for code, _ in list(countries):
        all_stats_per_country[code] = {
            "ixp_count": 0,
            "all_asns": None,
            "routed_asns": None,
            "member_asns": set(),
            "member_and_customer_asns": set(),
            "total_capacity": 0,
        }
    # Ensure we load the state of all IXPs as they were on the stats date
    ixps = es_app.get_all_ixps(stats_date)
    ixps_last_month = es_app.get_all_ixps(date_last_month)
    for ixp in ixps:
        # We always save the stats per IXP after their created date so we can track stats across time (e.g. if an IXP becomes inactive then active again)
        isoc_id = es_app.find_isoc_id(ixp.id)
        try:
            ixp_last_month = next(i for i in ixps_last_month if i.id == ixp.id)
        except StopIteration:
            ixp_last_month = None
        members = ixp.get_members()
        members_last_month = ixp_last_month.get_members() if ixp_last_month else {}
        member_asns = list(members.keys())
        member_count = len(member_asns)
        total_capacity = sum([m.port_speed for m in members.values()])
        rs_peers = [m for m in members if members[m].is_rs_peer]
        rs_peering_rate = (len(rs_peers) / member_count) if member_count > 0 else 0
        country_routed_asns = lookup.get_routed_asns_for_country(
            ixp.country_code, stats_date
        )
        domestic_network_membership = calculate_local_asns_members_rate(
            member_asns, country_routed_asns
        )
        customer_asns = lookup.get_customer_asns(member_asns, stats_date)
        domestic_network_coverage = calculate_local_asns_members_rate(
            member_asns + customer_asns, country_routed_asns
        )
        members_12_months_ago = ixp.get_members(as_at=date_12_months_ago)
        member_asns_12_months_ago = members_12_months_ago.keys()
        members_left_in_last_12_months = [
            asn for asn in member_asns_12_months_ago if asn not in member_asns
        ]
        members_joined_in_last_12_months = [
            asn for asn in member_asns if asn not in member_asns_12_months_ago
        ]
        rs_peers_last_month = [
            m for m in members_last_month if members_last_month[m].is_rs_peer
        ]
        rs_peered_members = [m for m in rs_peers if m not in rs_peers_last_month]
        rs_depeered_members = [m for m in rs_peers_last_month if m not in rs_peers]
        num_members_last_month = len(members_last_month.keys())
        growth_members = member_count - num_members_last_month
        StatsPerIXP.objects.update_or_create(
            ixp=isoc_id,
            stats_date=stats_date.date(),
            defaults={
                "members": member_count,
                "capacity": (total_capacity / 1000),
                "domestic_network_membership": domestic_network_membership,
                "domestic_network_coverage": domestic_network_coverage,
                "rs_peering_rate": rs_peering_rate,
                "members_joined_last_12_months": len(members_joined_in_last_12_months),
                "members_left_last_12_months": len(members_left_in_last_12_months),
                "monthly_members_change": growth_members,
                "monthly_members_change_percent": calculate_growth_members_percent(
                    growth_members, num_members_last_month
                ),
                "monthly_rs_peered_members_count": len(rs_peered_members),
                "monthly_rs_depeered_members_count": len(rs_depeered_members),
                "monthly_rs_peered_members": rs_peered_members,
                "monthly_rs_depeered_members": rs_depeered_members,
                "last_generated": date_now,
            },
        )
        if all_stats_per_country.get(ixp.country_code, None) is None:
            logger.warning(
                "IXP has possible invalid country",
                extra={"ixp": isoc_id, "country": ixp.country_code},
            )
        if ixp.active_status:
            all_stats_per_country[ixp.country_code]["ixp_count"] += 1
            all_stats_per_country[ixp.country_code]["member_asns"] |= set(member_asns)
            all_stats_per_country[ixp.country_code]["member_and_customer_asns"] |= set(
                member_asns
            )
            all_stats_per_country[ixp.country_code]["member_and_customer_asns"] |= set(
                customer_asns
            )
            # We count capacity for all members, i.e. an ASN member at 2 IXPs will have capacity at each included in the sum
            all_stats_per_country[ixp.country_code]["total_capacity"] += total_capacity
    for code, _ in list(countries):
        country_stats = all_stats_per_country[code]
        if country_stats.get("all_asns") is None:
            country_stats["all_asns"] = lookup.get_asns_for_country(code, stats_date)
        if country_stats.get("routed_asns") is None:
            country_stats["routed_asns"] = lookup.get_routed_asns_for_country(
                code, stats_date
            )
        local_routed_asns_members_rate = calculate_local_asns_members_rate(
            country_stats["member_asns"],
            list(country_stats["routed_asns"] or []),
        )
        local_routed_asns_members_customers_rate = calculate_local_asns_members_rate(
            country_stats["member_and_customer_asns"],
            list(country_stats["routed_asns"] or []),
        )
        StatsPerCountry.objects.update_or_create(
            country_code=code,
            stats_date=stats_date.date(),
            defaults={
                "ixp_count": country_stats["ixp_count"],
                "routed_asn_count": len(country_stats["routed_asns"] or []),
                "member_count": len(country_stats["member_asns"]),
                "domestic_network_membership": local_routed_asns_members_rate,
                "domestic_network_coverage": local_routed_asns_members_customers_rate,
                "total_capacity": (country_stats["total_capacity"] / 1000),
                "last_generated": date_now,
            },
        )


def calculate_growth_members_percent(
    growth_members: int, num_members_last_month: int
) -> float:
    if not growth_members:
        return 0.0
    elif not num_members_last_month:
        return 1.0
    return growth_members / num_members_last_month


def calculate_local_asns_members_rate(
    member_asns: Iterable[int], country_asns: list[int]
) -> float:
    if len(country_asns) == 0:
        return 0
    # Ignore the current country for a member ASN (as that might have changed) but just get all current members
    # that are in the list of ASNs registered to the country at the time
    members_in_country = [asn for asn in member_asns if asn in country_asns]
    return len(members_in_country) / len(country_asns)
