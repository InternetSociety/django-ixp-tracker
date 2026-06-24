import pytest
from faker.proxy import Faker

from ixp_tracker.ixp_tracker_aggregates import (
    NetworkType,
    PeeringPolicy,
)
from tests.fixtures import create_asn, MemoryEventStore, build_app

pytestmark = pytest.mark.django_db


def test_registers_asn(faker: Faker):
    app, _ = build_app()

    as_number = faker.random_number(digits=5)
    network_type = faker.random_element(NetworkType)
    name = faker.company()
    peering_policy = faker.random_element(PeeringPolicy)
    peeringdb_id = faker.random_number(digits=3)
    asn = app.import_asn(
        as_number,
        name,
        network_type,
        peering_policy,
        peeringdb_id,
        faker.country_code(),
        faker.pybool(),
        faker.pylist(nb_elements=10, variable_nb_elements=True, value_types=[int]),
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
    new_is_routed = not asn.is_routed
    new_customer_asns = faker.pylist(
        nb_elements=10, variable_nb_elements=True, value_types=[int]
    )
    app.import_asn(
        asn.number,
        new_name,
        new_network_policy,
        new_peering_policy,
        asn.peeringdb_id,
        new_country,
        new_is_routed,
        new_customer_asns,
    )

    [_event_created, update_event] = mes.events
    assert update_event.event_type == "ASNUpdated"
    assert update_event.data["name"] == new_name
    assert update_event.data["is_routed"] == new_is_routed
    assert update_event.data["customer_asns"] == new_customer_asns


def test_does_not_update_fields_if_not_changed(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn = create_asn(faker, es)

    app.import_asn(
        asn.number,
        asn.name + "X",
        asn.network_type,
        asn.peering_policy,
        asn.peeringdb_id,
        asn.country_code,
        asn.is_routed,
        asn.customer_asns,
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

    app.import_asn(
        asn.number,
        asn.name,
        asn.network_type,
        asn.peering_policy,
        asn.peeringdb_id + 1,
        asn.country_code,
        asn.is_routed,
        asn.customer_asns,
    )

    [_event_created, update_event] = mes.events

    assert update_event.event_type == "ASNPeeringDbIdChanged"
