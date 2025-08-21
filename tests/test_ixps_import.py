from datetime import datetime, timezone

import pytest

from ixp_tracker import importers
from ixp_tracker.models import IXP
from tests.fixtures import PeeringIXFactory

pytestmark = pytest.mark.django_db


def test_with_no_data_does_nothing():
    importers.process_ixp_data(datetime.now(timezone.utc))([])

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_imports_a_new_ixp():
    importers.process_ixp_data(datetime.now(timezone.utc))([PeeringIXFactory()])

    ixps = IXP.objects.all()
    assert len(ixps) == 1


def test_updates_an_existing_ixp():
    new_data = PeeringIXFactory()
    IXP(peeringdb_id=new_data["id"], last_active=datetime(year=2024, month=4, day=1).replace(tzinfo=timezone.utc))

    importers.process_ixp_data(datetime.now(timezone.utc))([new_data])

    ixps = IXP.objects.all()
    assert len(ixps) == 1
    assert ixps.first().last_active.date() == datetime.now(timezone.utc).date()
    assert ixps.first().name == new_data["name"]


def test_does_not_import_an_ixp_from_a_non_iso_country():
    new_data = PeeringIXFactory()
    new_data["country"] = "XK"  # XK is Kosovo, but it's not an official ISO code
    importers.process_ixp_data(datetime.now(timezone.utc))([new_data])

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_handles_errors_with_source_data():
    data_with_problems = PeeringIXFactory()
    data_with_problems["created"] = "abc"

    importers.process_ixp_data(datetime.now(timezone.utc))([data_with_problems])

    ixps = IXP.objects.all()
    assert len(ixps) == 0
