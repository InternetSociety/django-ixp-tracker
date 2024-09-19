import logging
from datetime import datetime, timezone
from typing import Dict, List, TypedDict, Union

from django_countries import countries
from django.db.models import Q

from ixp_tracker.importers import ASNGeoLookup
from ixp_tracker.models import IXP, IXPMember, IXPMembershipRecord, StatsPerCountry, StatsPerIXP

logger = logging.getLogger("ixp_tracker")


class CountryStats(TypedDict):
    all_asns: Union[List[int], None]
    member_asns: set
    total_capacity: int


def generate_stats(geo_lookup: ASNGeoLookup, stats_date: datetime = None):
    stats_date = stats_date or datetime.utcnow().replace(tzinfo=timezone.utc)
    stats_date = stats_date.replace(day=1)
    ixps = IXP.objects.filter(created__lte=stats_date).all()
    all_members = (IXPMember.objects
                   .filter(memberships__start_date__lte=stats_date)
                   .filter(Q(memberships__end_date=None) | Q(memberships__end_date__gte=stats_date))).all()
    all_stats_per_country: Dict[str, CountryStats] = {}
    for code, _ in list(countries):
        all_stats_per_country[code] = {
            "all_asns": None,
            "member_asns": set(),
            "total_capacity": 0
        }
    for ixp in ixps:
        logger.debug("Calculating growth stats for IXP", extra={"ixp": ixp.id})
        members = [member for member in all_members if member.ixp == ixp]
        member_count = len(members)
        capacity = 0
        for member in members:
            membership = (IXPMembershipRecord.objects
                .filter(start_date__lte=stats_date, member=member)
                .filter(Q(end_date=None) | Q(end_date__gte=stats_date))).first()
            if membership is not None:
                capacity += membership.speed
        ixp_country = ixp.country_code
        country_stats = all_stats_per_country.get(ixp_country)
        if country_stats is None:
            logger.warning("Country not found", extra={"country": ixp_country})
            country_stats = {
                "all_asns": None,
                "member_asns": set(),
                "total_capacity": 0
            }
            all_stats_per_country[ixp_country] = country_stats
        if country_stats.get("all_asns") is None:
            all_stats_per_country[ixp_country]["all_asns"] = geo_lookup.get_asns_for_country(ixp_country, stats_date)
        member_asns = [member.asn.number for member in members]
        local_asns_members_rate = calculate_local_asns_members_rate(member_asns, all_stats_per_country[ixp_country]["all_asns"])
        StatsPerIXP.objects.update_or_create(
            ixp=ixp,
            stats_date=stats_date.date(),
            defaults={
                "ixp": ixp,
                "stats_date": stats_date.date(),
                "members": member_count,
                "capacity": (capacity/1000),
                "local_asns_members_rate": local_asns_members_rate,
            }
        )
        # We only count unique ASNs that are members of an IXP in a country
        all_stats_per_country[ixp_country]["member_asns"] |= set(member_asns)
        # But we count capacity for all members, i.e. an ASN member at 2 IXPs will have capacity at each included in the sum
        all_stats_per_country[ixp_country]["total_capacity"] += capacity
    for code, _ in list(countries):
        country_stats = all_stats_per_country[code]
        if country_stats.get("all_asns") is None:
            country_stats["all_asns"] = geo_lookup.get_asns_for_country(code, stats_date)
        local_asns_members_rate = calculate_local_asns_members_rate(country_stats["member_asns"], country_stats["all_asns"])
        StatsPerCountry.objects.update_or_create(
            country_code=code,
            stats_date=stats_date.date(),
            defaults={
                "asn_count": len(country_stats["all_asns"]),
                "member_count": len(country_stats["member_asns"]),
                "asns_ixp_member_rate": local_asns_members_rate,
                "total_capacity": (country_stats["total_capacity"]/1000),
            }
        )


def calculate_local_asns_members_rate(member_asns: List[int], country_asns: [int]) -> float:
    if len(country_asns) == 0:
        return 0
    # Ignore the current country for a member ASN (as that might have changed) but just get all current members
    # that are in the list of ASNs registered to the country at the time
    members_in_country = [asn for asn in member_asns if asn in country_asns]
    return len(members_in_country) / len(country_asns)
