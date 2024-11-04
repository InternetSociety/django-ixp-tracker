from datetime import datetime

from ixp_tracker.models import ASN, IXP


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
        created="2019-01-01",
        last_updated="2024-05-01"
    )
    asn.save()
    return asn


def create_ixp_fixture(peering_db_id: int, country = "MM"):
    ixp = IXP(
        name="Old name",
        long_name="Network Name",
        city="Aberdeen",
        website="",
        active_status=True,
        peeringdb_id=peering_db_id,
        country_code=country,
        created=datetime(year=2020,month=10,day=1),
        last_updated=datetime(year=2023,month=10,day=1),
        last_active=datetime(year=2024, month=4, day=1)
    )
    ixp.save()
    return ixp
