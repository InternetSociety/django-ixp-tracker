from datetime import datetime

import pytest

from ixp_tracker import importers
from ixp_tracker.models import IXP

pytestmark = pytest.mark.django_db

dummy_ixp_data = {
    "id": 1,
    "name": "City IX",
    "name_long": "City Internet Exchange Point",
    "city": "City",
    "country": "AF",
    "website": "http://example.com",
    "created": "2019-08-24T14:15:22Z",
    "updated": "2019-08-24T14:15:22Z",
}


def test_with_no_data_does_nothing():
    importers.process_ixp_data(datetime.utcnow())([])

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_imports_a_new_ixp():
    importers.process_ixp_data(datetime.utcnow())([dummy_ixp_data])

    ixps = IXP.objects.all()
    assert len(ixps) == 1


def test_updates_an_existing_ixp():
    ixp = IXP(
        name="Old name",
        long_name=dummy_ixp_data["name_long"],
        city=dummy_ixp_data["city"],
        website=dummy_ixp_data["website"],
        active_status=True,
        peeringdb_id=dummy_ixp_data["id"],
        country_code=dummy_ixp_data["country"],
        created=dummy_ixp_data["created"],
        last_updated=dummy_ixp_data["updated"],
        last_active=datetime(year=2024, month=4, day=1)
    )
    ixp.save()

    importers.process_ixp_data(datetime.utcnow())([dummy_ixp_data])

    ixps = IXP.objects.all()
    assert len(ixps) == 1
    assert ixps.first().last_active.date() == datetime.utcnow().date()
    assert ixps.first().name == dummy_ixp_data["name"]


def test_does_not_import_an_ixp_from_a_non_iso_country():
    dummy_ixp_data["country"] = "XK"  # XK is Kosovo, but it's not an official ISO code
    importers.process_ixp_data(datetime.utcnow())([dummy_ixp_data])

    ixps = IXP.objects.all()
    assert len(ixps) == 0


def test_handles_errors_with_source_data():
    data_with_problems = dummy_ixp_data
    data_with_problems["created"] = "abc"

    importers.process_ixp_data(datetime.utcnow())([data_with_problems])

    ixps = IXP.objects.all()
    assert len(ixps) == 0
