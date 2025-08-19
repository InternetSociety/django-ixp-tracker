from datetime import datetime, timezone

from ixp_tracker.models import ASN, IXP, IXPMember, IXPMembershipRecord


def create_asn_fixture(as_number: int, country: str = "CH"):
    asn = ASN.objects.filter(number=as_number)
    if len(asn) > 0:
        return asn.first()
    asn = ASN(
        name="Network Org",
        number=as_number,
        peeringdb_id=5,
        network_type="other",
        registration_country_code=country,
        created=datetime(year=2019, month=1, day=1, tzinfo=timezone.utc),
        last_updated=datetime(year=2024, month=5, day=1, tzinfo=timezone.utc),
    )
    asn.save()
    return asn


def create_ixp_fixture(peering_db_id: int, country = "MM", last_active: datetime = None):
    last_active = last_active or datetime.now(timezone.utc)
    ixp = IXP(
        name="Old name",
        long_name="Network Name",
        city="Aberdeen",
        website="",
        active_status=True,
        peeringdb_id=peering_db_id,
        country_code=country,
        created=datetime(year=2020,month=10,day=1, tzinfo=timezone.utc),
        last_updated=datetime(year=2024, month=4, day=1, tzinfo=timezone.utc),
        last_active=last_active
    )
    ixp.save()
    return ixp


def create_member_fixture(ixp, as_number, speed = 10000, is_rs_peer = False, date_left = None, member_since = None, asn_country = "CH"):
    last_active = date_left or datetime.now(timezone.utc)
    member_since = member_since or datetime(year=2024, month=4, day=1).date()
    asn = create_asn_fixture(as_number, asn_country)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=datetime.now(timezone.utc),
        last_active=last_active
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=member_since,
        is_rs_peer=is_rs_peer,
        speed=speed,
        end_date=date_left
    )
    membership.save()
    return member
