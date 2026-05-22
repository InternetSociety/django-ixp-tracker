import json
from datetime import datetime, timezone

import pytest
import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers
from ixp_tracker.ixp_tracker import NetworkType, PeeringPolicy

from .fixtures import ASNFactory, PeeringASNFactory, build_app

pytestmark = pytest.mark.django_db


class TestLookup:
    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        assert as_at <= datetime.now(timezone.utc)
        assert asn > 0
        return "AU"

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass


def test_with_empty_response_does_nothing():
    app = build_app()
    processor = importers.process_asn_data(TestLookup(), app)
    processor([])

    asns = app.get_all_asns()
    assert len(asns) == 0


def test_with_no_existing_data_gets_all_data():
    with responses.RequestsMock() as rsps:
        app = build_app()
        rsps.get(url=IXP_TRACKER_PEERING_DB_URL + "/net?limit=200&skip=0", body="")
        importers.import_asns(TestLookup(), False, es_app=app)

        asns = app.get_all_asns()
        assert len(asns) == 0


def test_imports_new_asn():
    app = build_app()
    processor = importers.process_asn_data(TestLookup(), app)
    processor([PeeringASNFactory()])

    asns = app.get_all_asns()
    assert len(asns) == 1


def test_uses_defaults_for_network_type_and_peering_policy_if_invalid():
    app = build_app()
    processor = importers.process_asn_data(TestLookup(), app)
    asn_data = PeeringASNFactory()
    asn_data["info_type"] = "foobar"
    asn_data["policy_general"] = "foobar"
    processor([asn_data])

    asns = app.get_all_asns()
    assert len(asns) == 1
    asn = asns.pop(0)
    assert asn.network_type == NetworkType.UNKNOWN
    assert asn.peering_policy == PeeringPolicy.UNKNOWN


def test_updates_existing_data():
    updated_asn_data = PeeringASNFactory()
    ASNFactory(
        number=updated_asn_data["asn"],
        peeringdb_id=updated_asn_data["id"],
        last_updated=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )
    with responses.RequestsMock() as rsps:
        app = build_app()
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL
            + "/net?updated__gte=2024-05-01&limit=200&skip=0",
            body=json.dumps({"data": [updated_asn_data]}),
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL
            + "/net?updated__gte=2024-05-01&limit=200&skip=200",
            body=json.dumps({"data": []}),
        )
        importers.import_asns(TestLookup(), False, es_app=app)

        asns = app.get_all_asns()
        assert len(asns) == 1
        updated = asns.pop(0)
        assert updated.name == updated_asn_data["name"]
        assert updated.country_code == "AU"


def test_handles_errors_with_source_data():
    data_with_problems = PeeringASNFactory()
    data_with_problems["updated"] = "abc"
    data_with_problems["asn"] = "foobar"

    app = build_app()
    processor = importers.process_asn_data(TestLookup(), app)
    processor([data_with_problems])

    asns = app.get_all_asns()
    assert len(asns) == 0
