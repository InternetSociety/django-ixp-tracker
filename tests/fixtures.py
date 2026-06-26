import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypedDict, Optional, Any
from uuid import uuid4, UUID

import factory
from faker import Faker
from typing_extensions import NotRequired

from ixp_tracker.data_lookup import AdditionalDataSources
from ixp_tracker.event_store import (
    DomainEvent,
    ValueNotChanged,
    Aggregate,
    Projection,
    EventStore,
    DjangoEventStore,
    EventStorePersistence,
    T,
)
from ixp_tracker.ixp_tracker import (
    IXPTracker,
)
from ixp_tracker.ixp_tracker_aggregates import (
    IXPCreated,
    IXPBecameActive,
    IXPMemberJoined,
    IXPMemberLeft,
    ASNCreated,
    IXP_TRACKER_EVENT_MAP,
    ASN,
    IXP,
    NetworkType,
    PeeringPolicy,
    stringify_date,
)
from ixp_tracker.ixp_tracker_projections import (
    ASNList,
    IXPIdMapProjection,
    IXPsLastUpdatedProjection,
)
import ixp_tracker.models as legacy
from ixp_tracker.models import (
    StatsPerCountryLegacy,
    StatsPerIXPLegacy,
    StoredEvent,
    IXPIdMap,
)


class MemberProperties(TypedDict):
    last_active: NotRequired[datetime]
    last_updated: NotRequired[datetime]


class MembershipProperties(TypedDict):
    end_date: NotRequired[datetime]
    start_date: NotRequired[datetime]
    speed: NotRequired[int]
    is_rs_peer: NotRequired[bool]


def create_member_fixture(
    ixp,
    asn=None,
    quantity=1,
    membership_properties: MembershipProperties | None = None,
    member_properties: MemberProperties | None = None,
):
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
        model = legacy.ASN

    name = factory.Faker("nic_handle", suffix="FAKE")
    number = factory.Faker("random_number", digits=5)
    peeringdb_id = factory.Faker("random_number", digits=3)
    network_type = factory.Faker(
        "random_element", elements=[e[0] for e in legacy.ASN.NETWORK_TYPE_CHOICES]
    )
    peering_policy = factory.Faker(
        "random_element", elements=[e[0] for e in legacy.ASN.PEERING_POLICY_CHOICES]
    )
    registration_country_code = factory.Faker("country_code")
    created = factory.Faker(
        "date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    last_updated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


class IXPFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = legacy.IXP

    name = factory.LazyAttribute(lambda obj: f"{obj.city} - IX")
    long_name = factory.LazyAttribute(lambda obj: f"{obj.city} Internet Exchange Point")
    city = factory.Faker("city")
    website = factory.Faker("url", schemes=["https"])
    active_status = factory.Faker("pybool")
    manrs_participant = factory.Faker("pybool")
    anchor_host = factory.Faker("pybool")
    physical_locations = factory.Faker("random_number", digits=2)
    peeringdb_id = factory.Faker("random_number", digits=3)
    org_id = factory.Faker("random_number", digits=3)
    country_code = factory.Faker("country_code")
    created = factory.Faker(
        "date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    last_updated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )
    last_active = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


class IXPMemberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = legacy.IXPMember

    ixp = None
    asn = None
    last_updated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )
    last_active = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


class IXPMembershipRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = legacy.IXPMembershipRecord

    member = None
    start_date = factory.Faker(
        "date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    is_rs_peer = factory.Faker("pybool")
    speed = factory.Faker("random_number", digits=6)
    end_date = None


class PeeringASNFactory(factory.DictFactory):
    id = factory.Faker("random_number", digits=3)
    asn = factory.Faker("random_number", digits=5)
    name = factory.Faker("nic_handle", suffix="FAKE")
    info_type = factory.Faker(
        "random_element", elements=[e[1] for e in legacy.ASN.NETWORK_TYPE_CHOICES]
    )
    policy_general = factory.Faker(
        "random_element", elements=[e[1] for e in legacy.ASN.PEERING_POLICY_CHOICES]
    )
    created = factory.LazyAttribute(
        lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    updated = factory.LazyAttribute(
        lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    class Params:
        created_date = factory.Faker(
            "date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
        )
        updated_date = factory.Faker(
            "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
        )


class PeeringIXFactory(factory.DictFactory):
    id = factory.Faker("random_number", digits=3)
    name = factory.LazyAttribute(lambda obj: f"{obj.city} - IX")
    name_long = factory.LazyAttribute(lambda obj: f"{obj.city} Internet Exchange Point")
    org_id = factory.Faker("random_number", digits=3)
    city = factory.Faker("city")
    country = factory.Faker("country_code")
    website = factory.Faker("url", schemes=["https"])
    fac_count = factory.Faker("random_number", digits=2)
    created = factory.LazyAttribute(
        lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    updated = factory.LazyAttribute(
        lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    class Params:
        created_date = factory.Faker(
            "date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
        )
        updated_date = factory.Faker(
            "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
        )


class PeeringNetIXLANFactory(factory.DictFactory):
    asn = factory.Faker("random_number", digits=5)
    ix_id = factory.Faker("random_number", digits=3)
    created = factory.LazyAttribute(
        lambda obj: obj.created_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    updated = factory.LazyAttribute(
        lambda obj: obj.updated_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    is_rs_peer = factory.Faker("pybool")
    speed = factory.Faker("random_number", digits=6)

    class Params:
        created_date = factory.Faker(
            "date_time_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
        )
        updated_date = factory.Faker(
            "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
        )


class StatsPerIXPLegacyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StatsPerIXPLegacy

    ixp = None
    stats_date = factory.Faker(
        "date_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    capacity = factory.Faker("random_number", digits=5)
    members = factory.Faker("random_number", digits=3)
    local_asns_members_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    local_routed_asns_members_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    local_routed_asns_members_customers_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    rs_peering_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    members_joined_last_12_months = factory.Faker("random_number", digits=2)
    members_left_last_12_months = factory.Faker("random_number", digits=2)
    monthly_members_change = factory.Faker("random_number", digits=2)
    monthly_members_change_percent = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    last_generated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


class MockLookup(AdditionalDataSources):
    def __init__(
        self,
        asns: list[int] | None = None,
        routed_asns: list[int] | None = None,
        customer_asns: list[int] | None = None,
        manrs_participants: list[int] | None = None,
        anchor_hosts: list[int] | None = None,
        default_country: str = "US",
        default_status: str = "assigned",
    ):
        self.asns = asns or []
        self.routed_asns = routed_asns or []
        self.customer_asns = customer_asns or []
        self.manrs_participants = manrs_participants or []
        self.anchor_hosts = anchor_hosts or []
        self.default_country = default_country
        self.default_status = default_status

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        return self.default_country

    def get_status(self, asn: int, as_at: datetime) -> str:
        assert as_at <= datetime.now(timezone.utc)
        assert asn > 0
        return self.default_status

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


class StatsPerCountryLegacyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StatsPerCountryLegacy

    country_code = factory.Faker("country_code")
    stats_date = factory.Faker(
        "date_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    ixp_count = factory.Faker("random_int", max=200)
    asn_count = factory.Faker("random_int", max=1000)
    routed_asn_count = factory.Faker("random_int", max=800)
    member_count = factory.Faker("random_int", max=500)
    asns_ixp_member_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    routed_asns_ixp_member_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    routed_asns_ixp_member_customers_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    total_capacity = factory.Faker("random_number", digits=5)
    last_generated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


# Fixtures for event sourcing


class StatsPerIXPFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = legacy.StatsPerIXP

    ixp = None
    stats_date = factory.Faker(
        "date_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    capacity = factory.Faker("random_number", digits=5)
    members = factory.Faker("random_number", digits=3)
    domestic_network_membership = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    domestic_network_coverage = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    rs_peering_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    members_joined_last_12_months = factory.Faker("random_number", digits=2)
    members_left_last_12_months = factory.Faker("random_number", digits=2)
    monthly_members_change = factory.Faker("random_number", digits=2)
    monthly_members_change_percent = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    last_generated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


class StatsPerCountryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = legacy.StatsPerCountry

    country_code = factory.Faker("country_code")
    stats_date = factory.Faker(
        "date_between", start_date="-1y", end_date="-4w", tzinfo=timezone.utc
    )
    ixp_count = factory.Faker("random_int", max=200)
    routed_asn_count = factory.Faker("random_int", max=800)
    member_count = factory.Faker("random_int", max=500)
    domestic_network_membership = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    domestic_network_coverage = factory.Faker(
        "pyfloat", left_digits=1, right_digits=4, positive=True, max_value=1
    )
    total_capacity = factory.Faker("random_number", digits=5)
    last_generated = factory.Faker(
        "date_time_between", start_date="-4w", end_date="-1w", tzinfo=timezone.utc
    )


class StoredEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StoredEvent

    aggregate_id = factory.Faker("uuid4")
    aggregate_type = factory.Faker("word")
    event_date = factory.Faker(
        "date_time_between", start_date="-1d", tzinfo=timezone.utc
    )
    event_type = factory.Faker("word")
    event_sequence = factory.Faker("random_int", max=200)
    data: dict[str, Any] = {}


class IXPIdMapFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IXPIdMap

    aggregate_id = factory.Faker("uuid4")
    peeringdb_id = None


@dataclass
class CreatedTestAggregate(DomainEvent):
    foo: str


@dataclass
class TestAggregateUpdated(DomainEvent):
    __test__ = False
    foo: Optional[str] | ValueNotChanged = ValueNotChanged()
    bar: str | ValueNotChanged = ValueNotChanged()


TEST_EVENT_MAP = {
    CreatedTestAggregate.__name__: CreatedTestAggregate,
    TestAggregateUpdated.__name__: TestAggregateUpdated,
}


class TestAggregate(Aggregate):
    __test__ = False
    foo: str | None
    bar: Optional[str] = None

    def created(self, event: CreatedTestAggregate):
        self.foo = event.foo

    def updated(self, event: TestAggregateUpdated):
        self.foo = event.foo if not isinstance(event.foo, ValueNotChanged) else self.foo
        self.bar = event.bar if not isinstance(event.bar, ValueNotChanged) else self.bar


class SecondAggregate(Aggregate):
    foo: str

    def created(self, event: CreatedTestAggregate):
        self.foo = event.foo


class TestProjection(Projection):
    __test__ = False
    aggregate_types = [TestAggregate.__name__]
    events = [CreatedTestAggregate.__name__]

    handled = False

    def do_handle(self, event: StoredEvent, aggregate: Aggregate):
        self.handled = True


class MemoryEventStore(EventStorePersistence):
    def __init__(self):
        self.events: list[StoredEvent] = []
        self.sequence: dict[UUID, int] = {}
        self.snapshots: dict[UUID, tuple[str, int, datetime]] = {}
        self.snapshots_read: list[UUID] = []

    def get_event_sequence(self, event: DomainEvent, aggregate_id: UUID) -> int:
        if self.sequence.get(aggregate_id) is None:
            self.sequence[aggregate_id] = 0
        self.sequence[aggregate_id] = self.sequence[aggregate_id] + 1
        return self.sequence[aggregate_id]

    def save_event(self, event: StoredEvent):
        self.events.append(event)

    def get_aggregate_events(
        self,
        aggregate_id: UUID,
        aggregate_type: type[T],
        sequence: int | None,
        as_at: datetime | None = None,
    ) -> list[StoredEvent]:
        events = [e for e in self.events if e.aggregate_id == aggregate_id]
        if sequence is not None:
            events = [e for e in events if e.event_sequence > sequence]
        if as_at is not None:
            events = [e for e in events if e.event_date <= as_at]
        return events

    def get_all(
        self, aggregate_type: type[T], as_at: datetime | None = None
    ) -> list[UUID]:
        aggregates = set(
            [
                e.aggregate_id
                for e in self.events
                if e.aggregate_type == aggregate_type.__name__
                and (as_at is None or e.event_date <= as_at)
            ]
        )
        return list(aggregates)

    def get_events(self) -> list[StoredEvent]:
        return self.events

    def save_snapshot(
        self, aggregate_id: UUID, data: dict, sequence: int, date_now: datetime
    ):
        self.snapshots[aggregate_id] = (json.dumps(data), sequence, date_now)

    def load_snapshot(
        self, aggregate_id: UUID, as_at: datetime | None = None
    ) -> tuple[dict, int] | tuple[None, None]:
        snapshot = self.snapshots.get(aggregate_id, None)
        if snapshot is None:
            return None, None
        self.snapshots_read.append(aggregate_id)
        return json.loads(snapshot[0]), snapshot[1]


def build_app(
    es_db: EventStorePersistence | None = None,
    lookup: AdditionalDataSources | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    es.add_listener(IXPsLastUpdatedProjection())
    app = IXPTracker(es, lookup or MockLookup())
    return app, es


def create_ixp_event(
    faker: Faker,
    created_date: datetime | None = None,
    country_code: str | None = None,
    peeringdb_id: int | None = None,
):
    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    peeringdb_id = peeringdb_id or faker.random_number(digits=3)
    return IXPCreated(
        name,
        long_name,
        city,
        peeringdb_id,
        faker.url(schemes=["https"]),
        False,
        country_code or faker.country_code(),
        stringify_date(
            created_date
            or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
        ),
        stringify_date(faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)),
        stringify_date(faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)),
        False,
        False,
        faker.random_number(digits=3),
        faker.random_number(digits=2),
    )


def create_ixp(
    faker: Faker,
    es: EventStore,
    active_status=False,
    created_date: datetime | None = None,
    country_code: str | None = None,
    peeringdb_id: int | None = None,
) -> IXP:
    ixp = IXP(id=uuid4())
    event = create_ixp_event(faker, created_date, country_code, peeringdb_id)
    ixp = es.store(ixp, event)
    if active_status:
        ixp = es.store(ixp, IXPBecameActive())
    return ixp


def create_asn(
    faker: Faker,
    es: EventStore,
    country_code: str | None = None,
    asn: int | None = None,
) -> ASN:
    as_number = asn or faker.random_number(digits=5)
    network_type = faker.random_element(NetworkType)
    name = faker.company()
    peering_policy = faker.random_element(PeeringPolicy)
    peeringdb_id = faker.random_number(digits=3)
    country_code = country_code or faker.country_code()
    asn_entity = ASN(id=uuid4())
    event = ASNCreated(
        as_number,
        name,
        network_type.value,
        peering_policy.value,
        peeringdb_id,
        country_code,
        faker.pybool(),
        faker.pylist(nb_elements=10, variable_nb_elements=True, value_types=[int]),
    )
    return es.store(asn_entity, event)


def create_member(
    faker: Faker, es: EventStore, ixp: IXP, asn: ASN, overrides=None
) -> IXP:
    overrides = overrides or {}
    properties = {
        "start_date": overrides.get("start_date")
        or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        "updated_date": overrides.get("updated_date")
        or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        "last_active": overrides.get("last_active")
        or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        "is_rs_peer": overrides.get("is_rs_peer", faker.boolean()),
        "port_speed": overrides.get("port_speed") or faker.random_number(digits=5),
    }
    event = IXPMemberJoined(
        asn.number,
        stringify_date(properties["start_date"]),
        stringify_date(properties["updated_date"]),
        stringify_date(properties["last_active"]),
        properties["is_rs_peer"],
        properties["port_speed"],
    )
    ixp = es.store(ixp, event)
    if overrides.get("end_date") is not None:
        left_event = IXPMemberLeft(
            asn.number, stringify_date(overrides.get("end_date"))
        )
        ixp = es.store(ixp, left_event)
    return ixp
