from uuid import UUID

import pytest
from faker.proxy import Faker

from ixp_tracker.event_store import (
    DjangoEventStore,
    EventStore,
    Event,
    EventStorePersistence,
)
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXP_TRACKER_EVENT_MAP,
    NetworkType,
    PeeringPolicy,
    ASNList,
    ASN,
)
from ixp_tracker.models import StoredEvent
from tests.fixtures import create_asn

pytestmark = pytest.mark.django_db


class MemoryEventStore(EventStorePersistence):
    events: list = []
    sequence = 0

    def __init__(self):
        self.events = []

    def get_event_sequence(self, event: Event) -> int:
        self.sequence = self.sequence + 1
        return self.sequence

    def save_event(self, event: StoredEvent):
        self.events.append(event)

    def get_aggregate_events(
        self, aggregate_id: UUID, aggregate_type: type[ASN]
    ) -> list[StoredEvent]:
        return self.events


def test_registers_asn(faker: Faker):
    app, _ = build_app()

    as_number = faker.random_number(digits=5)
    network_type = faker.random_element(NetworkType)
    name = faker.company()
    peering_policy = faker.random_element(PeeringPolicy)
    peeringdb_id = faker.random_number(digits=3)
    asn = app.register_asn(
        as_number,
        name,
        network_type,
        peering_policy,
        peeringdb_id,
        faker.country_code(),
    )

    assert asn.name == name
    assert asn.network_type == network_type
    assert asn.peering_policy == peering_policy

    asn_map = app.get_asn(as_number)
    assert asn_map is not None


def test_updates_asn(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    asn = create_asn(faker, es)

    new_name = asn.name + "X"
    new_network_policy = faker.random_element(NetworkType)
    new_peering_policy = faker.random_element(PeeringPolicy)
    new_country = faker.country_code()
    app.update_asn(
        asn,
        new_name,
        new_network_policy,
        new_peering_policy,
        asn.peeringdb_id,
        new_country,
    )

    [_event_created, update_event] = mes.events
    assert update_event.event_type == "ASNUpdated"
    assert update_event.data["name"] == new_name


def test_does_not_update_fields_if_not_changed(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn = create_asn(faker, es)

    app.update_asn(
        asn,
        asn.name + "X",
        asn.network_type,
        asn.peering_policy,
        asn.peeringdb_id,
        asn.country_code,
    )

    [_event_created, update_event] = mes.events

    # Name is the only property that has changed so everything else should be marked as not changed
    assert update_event.data.get("network_type", None) is None
    assert update_event.data.get("peering_policy", None) is None
    assert update_event.data.get("country_code", None) is None


def test_records_peeringdb_id_change_as_separate_event(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn = create_asn(faker, es)

    app.update_asn(
        asn,
        asn.name,
        asn.network_type,
        asn.peering_policy,
        asn.peeringdb_id + 1,
        asn.country_code,
    )

    [_event_created, update_event] = mes.events

    assert update_event.event_type == "ASNPeeringDbIdChanged"


def build_app(es_db: EventStorePersistence = None) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(ASNList())
    app = IXPTracker(es)
    return app, es
