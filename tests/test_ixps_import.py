import json
from datetime import datetime

import pytest
import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
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


def test_with_no_import_date_queries_peering_db_directly():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=json.dumps({"data": []}),
        )
        result = importers.import_ixps()
        assert result


def test_returns_false_if_query_fails():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            status=404
        )
        result = importers.import_ixps()
        assert result is False


def test_with_empty_response_does_nothing():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=""
        )
        importers.import_ixps()

        ixps = IXP.objects.all()
        assert len(ixps) == 0


def test_imports_a_new_ixp():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=json.dumps({"data": [dummy_ixp_data]}),
        )
        importers.import_ixps()

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
        country=dummy_ixp_data["country"],
        created=dummy_ixp_data["created"],
        last_updated=dummy_ixp_data["updated"],
        last_active=datetime(year=2024, month=4, day=1)
    )
    ixp.save()

    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=json.dumps({"data": [dummy_ixp_data]}),
        )
        importers.import_ixps()

        ixps = IXP.objects.all()
        assert len(ixps) == 1
        assert ixps.first().last_active.date() == datetime.utcnow().date()
        assert ixps.first().name == dummy_ixp_data["name"]
