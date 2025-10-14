from datetime import datetime, timezone
from typing import TypedDict

import factory
from typing_extensions import NotRequired

from ixp_tracker.data_lookup import AdditionalDataSources
from ixp_tracker.models import ASN, IXP, IXPMember, IXPMembershipRecord, StatsPerCountry, StatsPerIXP


class MemberProperties(TypedDict):
    last_active: NotRequired[datetime]


class MembershipProperties(TypedDict):
    end_date: NotRequired[datetime]
    start_date: NotRequired[datetime]
    speed: NotRequired[int]
    is_rs_peer: NotRequired[bool]


def create_member_fixture(ixp, asn = None, quantity = 1, membership_properties: MembershipProperties = None, member_properties: MemberProperties = None):
    created = 0
    member = None
    member_properties = member_properties or {}
    membership_properties = membership_properties or {}
    while created < quantity:
        member_asn = asn or ASNFactory()
        member = IXPMemberFactory(ixp=ixp, asn=member_asn, **member_properties)
        IXPMembershipRecordFactory(member=member, **membership_properties)
        created += 1
    return member


class ASNFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ASN

    name = factory.Faker("nic_handle", suffix="FAKE")
    number = factory.Faker("random_number", digits=5)
    peeringdb_id = factory.Faker("random_number", digits=3)
    network_type = factory.Faker("random_element", elements=[e[0] for e in ASN.NETWORK_TYPE_CHOICES])
    peering_policy = factory.Faker("random_element", elements=[e[0] for e in ASN.PEERING_POLICY_CHOICES])
    registration_country_code = factory.Faker("country_code")
    created = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
    last_updated = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class IXPFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IXP

    name = factory.LazyAttribute(lambda obj: f"{obj.city} - IX")
    long_name = factory.LazyAttribute(lambda obj: f"{obj.city} Internet Exchange Point")
    city = factory.Faker("city")
    website = factory.Faker("url", schemes=["https"])
    active_status = factory.Faker("pybool")
    manrs_participant = factory.Faker("pybool")
    anchor_host = factory.Faker("pybool")
    peeringdb_id = factory.Faker("random_number", digits=3)
    org_id = factory.Faker("random_number", digits=3)
    country_code = factory.Faker("country_code")
    created = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
    last_updated = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)
    last_active = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class IXPMemberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IXPMember

    ixp = None
    asn = None
    last_updated = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)
    last_active = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class IXPMembershipRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IXPMembershipRecord

    member = None
    start_date = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
    is_rs_peer = factory.Faker("pybool")
    speed = factory.Faker("random_number", digits=6)
    end_date = None


class PeeringASNFactory(factory.DictFactory):
    id = factory.Faker("random_number", digits=3)
    asn = factory.Faker("random_number", digits=5)
    name = factory.Faker("nic_handle", suffix="FAKE")
    info_type = factory.Faker("random_element", elements=[e[0] for e in ASN.NETWORK_TYPE_CHOICES])
    policy_general = factory.Faker("random_element", elements=[e[0] for e in ASN.PEERING_POLICY_CHOICES])
    created = factory.LazyAttribute(lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated = factory.LazyAttribute(lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ"))


    class Params:
        created_date = factory.Faker("date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
        updated_date = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class PeeringIXFactory(factory.DictFactory):
    id = factory.Faker("random_number", digits=3)
    name = factory.LazyAttribute(lambda obj: f"{obj.city} - IX")
    name_long = factory.LazyAttribute(lambda obj: f"{obj.city} Internet Exchange Point")
    org_id = factory.Faker("random_number", digits=3)
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


class StatsPerIXPFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StatsPerIXP

    ixp = None
    stats_date = factory.Faker("date_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
    capacity = factory.Faker("random_number", digits=5)
    members = factory.Faker("random_number", digits=3)
    local_asns_members_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    local_routed_asns_members_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    local_routed_asns_members_customers_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    rs_peering_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    members_joined_last_12_months = factory.Faker("random_number", digits=2)
    members_left_last_12_months = factory.Faker("random_number", digits=2)
    monthly_members_change = factory.Faker("random_number", digits=2)
    monthly_members_change_percent = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    last_generated = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)


class MockLookup(AdditionalDataSources):

    def __init__(self, asns: list[int] = [], routed_asns: list[int] = [], customer_asns: list[int] = [], manrs_participants: list[int] = [], anchor_hosts: list[int] = []):
        self.asns = asns
        self.routed_asns = routed_asns
        self.customer_asns = customer_asns
        self.manrs_participants = manrs_participants
        self.anchor_hosts = anchor_hosts

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass

    def get_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
        return self.asns

    def get_routed_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
        return self.routed_asns

    def get_customer_asns(self, asns: list[int], as_at: datetime) -> list[int]:
        return self.customer_asns

    def get_manrs_participants(self, as_at: datetime) -> list[int]:
        return self.manrs_participants

    def get_atlas_anchor_hosts(self, as_at: datetime) -> list[int]:
        return self.anchor_hosts


class StatsPerCountryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StatsPerCountry

    country_code = factory.Faker("country_code")
    stats_date = factory.Faker("date_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc)
    ixp_count = factory.Faker("random_int", max=200)
    asn_count = factory.Faker("random_int", max=1000)
    routed_asn_count = factory.Faker("random_int", max=800)
    member_count = factory.Faker("random_int", max=500)
    asns_ixp_member_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    routed_asns_ixp_member_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    routed_asns_ixp_member_customers_rate = factory.Faker("pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1)
    total_capacity = factory.Faker("random_number", digits=5)
    last_generated = factory.Faker("date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc)
