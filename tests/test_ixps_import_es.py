from datetime import datetime, timezone

import pytest

from ixp_tracker.importers import process_ixp_data
from tests.fixtures import MockLookup, PeeringIXFactory, build_app

pytestmark = pytest.mark.django_db
IXP_TRACKER_ENABLE_EVENT_SOURCING = True


def test_with_no_data_does_nothing():
    app, _ = build_app()
    process_ixp_data([], datetime.now(timezone.utc), MockLookup(), app)

    assert len(app.get_all_ixps()) == 0


def test_imports_a_new_ixp():
    app, _ = build_app()
    process_ixp_data(
        [PeeringIXFactory()], datetime.now(timezone.utc), MockLookup(), app
    )

    ixps = app.get_all_ixps()
    assert len(ixps) == 1


def test_import_handles_missing_data():
    new_data = PeeringIXFactory()
    del new_data["fac_count"]
    app, _ = build_app()
    process_ixp_data([new_data], datetime.now(timezone.utc), MockLookup(), app)

    ixps = app.get_all_ixps()
    assert len(ixps) == 1


def test_updates_an_existing_ixp(faker):
    new_data = PeeringIXFactory()
    app, _ = build_app()
    city = faker.city()
    name = f"{city} - IX"
    long_name = f"{city} Internet Exchange Point"
    app.import_ixp(
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

    process_ixp_data(
        [new_data],
        datetime.now(timezone.utc),
        MockLookup(),
        app,
    )

    ixp = app.find_by_peeringdb_id(new_data["id"])
    assert ixp.last_active.date() == datetime.now(timezone.utc).date()
    assert ixp.name == new_data["name"]


def test_does_not_import_an_ixp_from_a_non_iso_country():
    new_data = PeeringIXFactory()
    new_data["country"] = "XK"  # XK is Kosovo, but it's not an official ISO code
    app, _ = build_app()
    process_ixp_data([new_data], datetime.now(timezone.utc), MockLookup(), app)

    ixps = app.get_all_ixps()
    assert len(ixps) == 0


def test_handles_errors_with_source_data():
    data_with_problems = PeeringIXFactory()
    data_with_problems["created"] = "abc"

    app, _ = build_app()
    process_ixp_data(
        [data_with_problems], datetime.now(timezone.utc), MockLookup(), app
    )

    ixps = app.get_all_ixps()
    assert len(ixps) == 0


def test_saves_manrs_participant():
    new_data = PeeringIXFactory()
    manrs_participants = [new_data["id"]]
    app, _ = build_app()
    process_ixp_data(
        [new_data],
        datetime.now(timezone.utc),
        MockLookup(manrs_participants=manrs_participants),
        app,
    )

    ixp = app.find_by_peeringdb_id(new_data["id"])
    assert ixp.manrs_participant


def test_saves_anchor_host():
    new_data = PeeringIXFactory()
    anchor_hosts = [new_data["id"]]
    app, _ = build_app()
    process_ixp_data(
        [new_data],
        datetime.now(timezone.utc),
        MockLookup(anchor_hosts=anchor_hosts),
        app,
    )

    ixp = app.find_by_peeringdb_id(new_data["id"])
    assert ixp.anchor_host
