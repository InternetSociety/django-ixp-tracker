from datetime import datetime, timezone

import pytest

from ixp_tracker import importers
from ixp_tracker.event_store import DjangoEventStore
from ixp_tracker.ixp_tracker import (
    IXPIdMapProjection,
    IXPTracker,
    IXP_TRACKER_EVENT_MAP,
)
from ixp_tracker.models import IXPIdMap
from tests.fixtures import MockLookup, PeeringIXFactory

pytestmark = pytest.mark.django_db
IXP_TRACKER_ENABLE_EVENT_SOURCING = True


def test_with_no_data_does_nothing():
    importers.process_ixp_data(
        datetime.now(timezone.utc), MockLookup(), IXP_TRACKER_ENABLE_EVENT_SOURCING
    )([])

    # We use the id map as a proxy as we expect one and only one map per imported IXP
    ixps = IXPIdMap.objects.all()
    assert len(ixps) == 0


def test_imports_a_new_ixp():
    importers.process_ixp_data(
        datetime.now(timezone.utc), MockLookup(), IXP_TRACKER_ENABLE_EVENT_SOURCING
    )([PeeringIXFactory()])

    ixps = IXPIdMap.objects.all()
    assert len(ixps) == 1
    ixp = ixps.first()
    assert ixp.aggregate_id


def test_updates_an_existing_ixp(faker):
    new_data = PeeringIXFactory()
    manrs_participants = [new_data["id"]]
    app = IXPTracker(DjangoEventStore(IXP_TRACKER_EVENT_MAP), IXPIdMapProjection())
    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    app.register_ixp(
        name,
        long_name,
        city,
        new_data["id"],
        faker.url(schemes=["https"]),
        faker.country_code(),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        datetime(year=2024, month=4, day=1).replace(tzinfo=timezone.utc, microsecond=1),
        False,
        False,
        faker.random_number(digits=3),
        faker.random_number(digits=2),
    )

    importers.process_ixp_data(
        datetime.now(timezone.utc),
        MockLookup(manrs_participants=manrs_participants),
        IXP_TRACKER_ENABLE_EVENT_SOURCING,
    )([new_data])

    ixp = app.find_by_peeringdb_id(new_data["id"])
    assert ixp.last_active.date() == datetime.now(timezone.utc).date()
    assert ixp.name == new_data["name"]


def test_does_not_import_an_ixp_from_a_non_iso_country():
    new_data = PeeringIXFactory()
    new_data["country"] = "XK"  # XK is Kosovo, but it's not an official ISO code
    importers.process_ixp_data(
        datetime.now(timezone.utc), MockLookup(), IXP_TRACKER_ENABLE_EVENT_SOURCING
    )([new_data])

    ixps = IXPIdMap.objects.all()
    assert len(ixps) == 0


def test_handles_errors_with_source_data():
    data_with_problems = PeeringIXFactory()
    data_with_problems["created"] = "abc"

    importers.process_ixp_data(
        datetime.now(timezone.utc), MockLookup(), IXP_TRACKER_ENABLE_EVENT_SOURCING
    )([data_with_problems])

    ixps = IXPIdMap.objects.all()
    assert len(ixps) == 0


def test_saves_manrs_participant():
    new_data = PeeringIXFactory()
    manrs_participants = [new_data["id"]]
    importers.process_ixp_data(
        datetime.now(timezone.utc),
        MockLookup(manrs_participants=manrs_participants),
        IXP_TRACKER_ENABLE_EVENT_SOURCING,
    )([new_data])

    app = IXPTracker(DjangoEventStore(IXP_TRACKER_EVENT_MAP), IXPIdMapProjection())
    ixp = app.find_by_peeringdb_id(new_data["id"])
    assert ixp.manrs_participant


def test_saves_anchor_host():
    new_data = PeeringIXFactory()
    anchor_hosts = [new_data["id"]]
    importers.process_ixp_data(
        datetime.now(timezone.utc),
        MockLookup(anchor_hosts=anchor_hosts),
        IXP_TRACKER_ENABLE_EVENT_SOURCING,
    )([new_data])

    app = IXPTracker(DjangoEventStore(IXP_TRACKER_EVENT_MAP), IXPIdMapProjection())
    ixp = app.find_by_peeringdb_id(new_data["id"])
    assert ixp.anchor_host
