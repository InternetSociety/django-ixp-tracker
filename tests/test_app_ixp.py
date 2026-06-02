from datetime import timezone

import pytest
from faker.proxy import Faker

from ixp_tracker.event_store import (
    DjangoEventStore,
    EventStore,
    EventStorePersistence,
)
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXPIdMapProjection,
    IXP_TRACKER_EVENT_MAP,
)
from tests.fixtures import create_ixp, MemoryEventStore, TestLookup

pytestmark = pytest.mark.django_db


def test_registers_ixp(faker: Faker):
    app, _ = build_app()

    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    peeringdb_id = faker.random_number(digits=3)
    ixp = app.register_ixp(
        name,
        long_name,
        city,
        peeringdb_id,
        faker.url(schemes=["https"]),
        faker.country_code(),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        False,
        False,
        faker.random_number(digits=3),
        faker.random_number(digits=2),
    )

    assert ixp.name == name
    assert ixp.long_name == long_name
    assert ixp.peeringdb_id == peeringdb_id

    isoc_id = app.find_by_peeringdb_id(peeringdb_id)
    assert isoc_id is not None


def test_updates_main_ixp_details(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)

    new_name = ixp.name + "X"
    new_long_name = ixp.long_name + "X"
    new_city = faker.city()
    new_website = faker.url(schemes=["https"])
    new_country = faker.country_code()
    app.update_ixp(
        ixp,
        new_name,
        new_long_name,
        new_city,
        new_website,
        new_country,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.random_number(digits=3),
        ixp.manrs_participant,
        ixp.anchor_host,
        ixp.physical_locations,
    )

    [_event_created, update_event, _last_active] = mes.events
    assert update_event.event_type == "IXPUpdated"
    assert update_event.data["name"] == new_name


def test_does_not_update_fields_if_not_changed(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    ixp = create_ixp(faker, es)

    app.update_ixp(
        ixp,
        ixp.name + "X",
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        ixp.org_id,
        False,
        False,
        ixp.physical_locations,
    )

    [_event_created, update_event, _last_active] = mes.events

    # Name is the only property that has changed so everything else should be marked as not changed
    assert update_event.data.get("long_name", None) is None
    assert update_event.data.get("city", None) is None
    assert update_event.data.get("website", None) is None
    assert update_event.data.get("country_code", None) is None
    assert update_event.data.get("created", None) is None
    assert update_event.data.get("last_updated", None) is None
    assert update_event.data.get("org_id", None) is None


def test_always_updates_last_active(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    ixp = create_ixp(faker, es)

    processing_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    ixp = app.update_ixp(
        ixp,
        ixp.name,
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        processing_date,
        ixp.org_id,
        False,
        False,
        ixp.physical_locations,
    )

    [_, last_active_update] = mes.events

    assert last_active_update.event_type == "IXPActiveInPeeringDb"
    assert ixp.last_active.date() == processing_date.date()


def test_registers_change_in_manrs_status(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    ixp.manrs_participant = False

    ixp = app.update_ixp(
        ixp,
        ixp.name,
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        ixp.org_id,
        True,
        False,
        ixp.physical_locations,
    )

    [_event_created, manrs_update, _last_active] = mes.events

    assert manrs_update.event_type == "ManrsStatusChange"
    assert ixp.manrs_participant


def test_registers_change_in_anchor_host(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)

    ixp = app.update_ixp(
        ixp,
        ixp.name,
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        ixp.org_id,
        ixp.manrs_participant,
        True,
        ixp.physical_locations,
    )

    [_event_created, anchor_host_update, _last_active] = mes.events

    assert anchor_host_update.event_type == "AnchorHostChange"
    assert ixp.anchor_host


def test_registers_change_in_location_count_if_both_values_exist(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)

    ixp = app.update_ixp(
        ixp,
        ixp.name,
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        ixp.org_id,
        ixp.manrs_participant,
        ixp.anchor_host,
        (ixp.physical_locations + 1),
    )

    [_event_created, physical_locations_update, _last_active] = mes.events

    assert physical_locations_update.event_type == "PhysicalLocationChange"
    assert ixp.anchor_host is False


def test_registers_no_change_in_location_count_if_new_value_is_none(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    original_value = ixp.physical_locations

    ixp = app.update_ixp(
        ixp,
        ixp.name,
        ixp.long_name,
        ixp.city,
        ixp.website,
        ixp.country_code,
        ixp.date_created,
        ixp.last_updated,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        ixp.org_id,
        ixp.manrs_participant,
        ixp.anchor_host,
        None,
    )

    [event_created, last_active] = mes.events

    assert event_created.event_type == "IXPCreated"
    assert last_active.event_type == "IXPActiveInPeeringDb"
    assert ixp.physical_locations == original_value


def build_app(
    es_db: EventStorePersistence | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    app = IXPTracker(es, TestLookup())
    return app, es
