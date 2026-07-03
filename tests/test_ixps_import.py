from datetime import datetime, timezone

import pytest

from ixp_tracker.importers import process_ixp_data
from ixp_tracker.models import IXP
from tests.fixtures import IXPFactory, MockLookup, PeeringIXFactory

pytestmark = pytest.mark.django_db


def test_with_no_data_does_nothing():
    process_ixp_data([], datetime.now(timezone.utc), MockLookup())

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_imports_a_new_ixp():
    process_ixp_data([PeeringIXFactory()], datetime.now(timezone.utc), MockLookup())

    ixps = IXP.objects.all()
    assert len(ixps) == 1
    ixp = ixps.first()
    assert not ixp.manrs_participant


def test_updates_an_existing_ixp():
    new_data = PeeringIXFactory()
    manrs_participants = [new_data["id"]]
    IXPFactory(
        peeringdb_id=new_data["id"],
        last_active=datetime(year=2024, month=4, day=1).replace(tzinfo=timezone.utc),
        manrs_participant=False,
    )

    process_ixp_data(
        [new_data],
        datetime.now(timezone.utc),
        MockLookup(manrs_participants=manrs_participants),
    )

    ixps = IXP.objects.all()
    assert len(ixps) == 1
    ixp = IXP.objects.first()
    assert ixp.last_active.date() == datetime.now(timezone.utc).date()
    assert ixp.name == new_data["name"]
    assert ixp.manrs_participant


def test_does_not_import_an_ixp_from_a_non_iso_country():
    new_data = PeeringIXFactory()
    new_data["country"] = "XK"  # XK is Kosovo, but it's not an official ISO code
    process_ixp_data([new_data], datetime.now(timezone.utc), MockLookup())

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_handles_errors_with_source_data():
    data_with_problems = PeeringIXFactory()
    data_with_problems["created"] = "abc"

    process_ixp_data([data_with_problems], datetime.now(timezone.utc), MockLookup())

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_saves_manrs_participant():
    new_data = PeeringIXFactory()
    manrs_participants = [new_data["id"]]
    process_ixp_data(
        [new_data],
        datetime.now(timezone.utc),
        MockLookup(manrs_participants=manrs_participants),
    )

    ixp = IXP.objects.first()
    assert ixp.manrs_participant


def test_saves_anchor_host():
    new_data = PeeringIXFactory()
    anchor_hosts = [new_data["id"]]
    process_ixp_data(
        [new_data], datetime.now(timezone.utc), MockLookup(anchor_hosts=anchor_hosts)
    )

    ixp = IXP.objects.first()
    assert ixp.anchor_host
