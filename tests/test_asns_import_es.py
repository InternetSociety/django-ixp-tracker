import pytest
import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers
from ixp_tracker.ixp_tracker_aggregates import NetworkType, PeeringPolicy

from .fixtures import PeeringASNFactory, build_app, TestLookup

pytestmark = pytest.mark.django_db


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


def test_updates_existing_data(faker):
    name = faker.nic_handle(suffix="FAKE")
    updated_asn_data = PeeringASNFactory(name=(name + "new"))
    app = build_app()
    app.import_asn(
        updated_asn_data["asn"],
        name,
        NetworkType.CONTENT,
        PeeringPolicy.OPEN,
        updated_asn_data["id"],
        faker.country_code(),
    )

    processor = importers.process_asn_data(TestLookup(default_country="AU"), app)
    processor([updated_asn_data])

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
