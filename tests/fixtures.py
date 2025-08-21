from datetime import datetime, timezone

import factory

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


class ASNFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ASN

    name = factory.Faker("nic_handle", suffix="FAKE")
    number = factory.Faker("random_number", digits=5)
    peeringdb_id = factory.Faker("random_number", digits=3)
    network_type = factory.Faker("random_element", elements=[e[0] for e in ASN.NETWORK_TYPE_CHOICES])
    registration_country_code = factory.Faker("country_code")
    created = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
    last_updated = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class PeeringASNFactory(factory.DictFactory):
    id = factory.Faker("random_number", digits=3)
    asn = factory.Faker("random_number", digits=5)
    name = factory.Faker("nic_handle", suffix="FAKE")
    info_type = factory.Faker("random_element", elements=[e[0] for e in ASN.NETWORK_TYPE_CHOICES])
    created = factory.LazyAttribute(lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated = factory.LazyAttribute(lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ"))


    class Params:
        created_date = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
        updated_date = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class PeeringIXFactory(factory.DictFactory):
    id = factory.Faker("random_number", digits=3)
    name = factory.LazyAttribute(lambda obj: f"{obj.city} - IX")
    name_long = factory.LazyAttribute(lambda obj: f"{obj.city} Internet Exchange Point")
    city = factory.Faker("city")
    country = factory.Faker("country_code")
    website = factory.Faker("url", schemes=["https"])
    created = factory.LazyAttribute(lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated = factory.LazyAttribute(lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ"))


    class Params:
        created_date = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
        updated_date = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class PeeringNetIXLANFactory(factory.DictFactory):
    asn = factory.Faker("random_number", digits=5)
    ix_id = factory.Faker("random_number", digits=3)
    created = factory.LazyAttribute(lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated = factory.LazyAttribute(lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    is_rs_peer = factory.Faker("pybool")
    speed = factory.Faker("random_number", digits=6)


    class Params:
        created_date = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
        updated_date = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)
