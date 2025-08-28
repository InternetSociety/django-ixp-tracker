import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, TypedDict, Union

from django_countries import countries
from django.db.models import Q

from ixp_tracker.importers import AdditionalDataSources, is_ixp_active
from ixp_tracker.models import IXP, IXPMember, IXPMembershipRecord, StatsPerCountry, StatsPerIXP

logger = logging.getLogger("ixp_tracker")


class CountryStats(TypedDict):
    ixp_count: int
    all_asns: Union[List[int], None]
    routed_asns: Union[List[int], None]
    member_asns: set
    member_and_customer_asns: set
    total_capacity: int


def generate_stats(lookup: AdditionalDataSources, stats_date: datetime = None):
    stats_date = stats_date or datetime.now(timezone.utc)
    stats_date = stats_date.replace(day=1)
    date_12_months_ago = stats_date.replace(year=(stats_date.year - 1))
    date_last_month = (stats_date - timedelta(days=1)).replace(day=1)
    ixps = IXP.objects.filter(created__lte=stats_date).all()
    all_members = (IXPMember.objects
                   .filter(
                        Q(memberships__start_date__lte=stats_date) &
                        (Q(memberships__end_date=None) | Q(memberships__end_date__gte=stats_date))
                    )).all()
    all_members_12_months_ago = (IXPMember.objects
                   .filter(
                        Q(memberships__start_date__lte=date_12_months_ago) &
                        (Q(memberships__end_date=None) | Q(memberships__end_date__gte=date_12_months_ago))
                    )).all()
    all_stats_per_country: Dict[str, CountryStats] = {}
    for code, _ in list(countries):
        all_stats_per_country[code] = {
            "ixp_count": 0,
            "all_asns": None,
            "routed_asns": None,
            "member_asns": set(),
            "member_and_customer_asns": set(),
            "total_capacity": 0
        }
    for ixp in ixps:
        logger.debug("Calculating growth stats for IXP", extra={"ixp": ixp.id})
        members = [member for member in all_members if member.ixp == ixp]
        members_12_months_ago = [member for member in all_members_12_months_ago if member.ixp == ixp]
        member_count = len(members)
        capacity = 0
        rs_peers = 0
        for member in members:
            # Make sure we get the relevant membership record for the stats_date
            membership = (IXPMembershipRecord.objects
                .filter(start_date__lte=stats_date, member=member)
                .filter(Q(end_date=None) | Q(end_date__gte=stats_date))).first()
            if membership is not None:
                capacity += membership.speed
                if membership.is_rs_peer:
                    rs_peers += 1
        ixp_country = ixp.country_code
        country_stats = all_stats_per_country.get(ixp_country)
        if country_stats is None:
            logger.warning("Country not found", extra={"country": ixp_country})
            country_stats = {
                "ixp_count": 0,
                "all_asns": None,
                "routed_asns": None,
                "member_asns": set(),
                "member_and_customer_asns": set(),
                "total_capacity": 0
            }
            all_stats_per_country[ixp_country] = country_stats
        if country_stats.get("all_asns") is None:
            all_stats_per_country[ixp_country]["all_asns"] = lookup.get_asns_for_country(ixp_country, stats_date)
        if country_stats.get("routed_asns") is None:
            all_stats_per_country[ixp_country]["routed_asns"] = lookup.get_routed_asns_for_country(ixp_country, stats_date)
        member_asns = [member.asn.number for member in members]
        member_asns_12_months_ago = [member.asn.number for member in members_12_months_ago]
        members_left = [asn for asn in member_asns_12_months_ago if asn not in member_asns]
        members_joined = [asn for asn in member_asns if asn not in member_asns_12_months_ago]
        customer_asns = lookup.get_customer_asns(member_asns, stats_date)
        members_and_customers = set(member_asns + customer_asns)
        local_asns_members_rate = calculate_local_asns_members_rate(member_asns, all_stats_per_country[ixp_country]["all_asns"])
        local_routed_asns_members_rate = calculate_local_asns_members_rate(member_asns, all_stats_per_country[ixp_country]["routed_asns"])
        local_routed_asns_members_customers_rate = calculate_local_asns_members_rate(members_and_customers, all_stats_per_country[ixp_country]["routed_asns"])
        rs_peering_rate = rs_peers / member_count if rs_peers else 0
        stats_last_month = StatsPerIXP.objects.filter(ixp=ixp, stats_date=date_last_month.date()).first()
        members_last_month = stats_last_month.members if stats_last_month else 0
        growth_members = member_count - members_last_month
        # We always save the stats per IXP so we can track stats across time (e.g. if an IXP becomes inactive then active again)
        StatsPerIXP.objects.update_or_create(
            ixp=ixp,
            stats_date=stats_date.date(),
            defaults={
                "ixp": ixp,
                "stats_date": stats_date.date(),
                "members": member_count,
                "capacity": (capacity/1000),
                "local_asns_members_rate": local_asns_members_rate,
                "local_routed_asns_members_rate": local_routed_asns_members_rate,
                "local_routed_asns_members_customers_rate": local_routed_asns_members_customers_rate,
                "rs_peering_rate": rs_peering_rate,
                "members_joined_last_12_months": len(members_joined),
                "members_left_last_12_months": len(members_left),
                "monthly_members_change": growth_members,
                "monthly_members_change_percent": (growth_members / members_last_month) if members_last_month > 0 else 1,
            }
        )
        # Only aggregate this IXP's stats into the country stats if it's active
        if is_ixp_active(members):
            all_stats_per_country[ixp_country]["ixp_count"] += 1
            # We only count unique ASNs that are members of an IXP in a country
            all_stats_per_country[ixp_country]["member_asns"] |= set(member_asns)
            all_stats_per_country[ixp_country]["member_and_customer_asns"] |= members_and_customers
            # But we count capacity for all members, i.e. an ASN member at 2 IXPs will have capacity at each included in the sum
            all_stats_per_country[ixp_country]["total_capacity"] += capacity
    for code, _ in list(countries):
        country_stats = all_stats_per_country[code]
        if country_stats.get("all_asns") is None:
            country_stats["all_asns"] = lookup.get_asns_for_country(code, stats_date)
        if country_stats.get("routed_asns") is None:
            country_stats["routed_asns"] = lookup.get_routed_asns_for_country(code, stats_date)
        local_asns_members_rate = calculate_local_asns_members_rate(country_stats["member_asns"], country_stats["all_asns"])
        local_routed_asns_members_rate = calculate_local_asns_members_rate(country_stats["member_asns"], country_stats["routed_asns"])
        local_routed_asns_members_customers_rate = calculate_local_asns_members_rate(country_stats["member_and_customer_asns"], country_stats["routed_asns"])
        StatsPerCountry.objects.update_or_create(
            country_code=code,
            stats_date=stats_date.date(),
            defaults={
                "ixp_count": country_stats["ixp_count"],
                "asn_count": len(country_stats["all_asns"]),
                "routed_asn_count": len(country_stats["routed_asns"]),
                "member_count": len(country_stats["member_asns"]),
                "asns_ixp_member_rate": local_asns_members_rate,
                "routed_asns_ixp_member_rate": local_routed_asns_members_rate,
                "routed_asns_ixp_member_customers_rate": local_routed_asns_members_customers_rate,
                "total_capacity": (country_stats["total_capacity"]/1000),
            }
        )


def calculate_local_asns_members_rate(member_asns: Iterable[int], country_asns: List[int]) -> float:
    if len(country_asns) == 0:
        return 0
    # Ignore the current country for a member ASN (as that might have changed) but just get all current members
    # that are in the list of ASNs registered to the country at the time
    members_in_country = [asn for asn in member_asns if asn in country_asns]
    return len(members_in_country) / len(country_asns)
