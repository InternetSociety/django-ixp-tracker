from datetime import datetime, timezone

import pytest
import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers
from ixp_tracker.data_lookup import ASNGeoLookup
from ixp_tracker.ixp_tracker_aggregates import NetworkType, PeeringPolicy

from .fixtures import PeeringASNFactory, build_app, TestLookup

pytestmark = pytest.mark.django_db
processing_date = datetime.now(timezone.utc)


def test_with_empty_response_does_nothing():
    app = build_app()
    processor = importers.process_asn_data(processing_date, TestLookup(), app)
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
    processor = importers.process_asn_data(processing_date, TestLookup(), app)
    processor([PeeringASNFactory()])

    asns = app.get_all_asns()
    assert len(asns) == 1


def test_uses_defaults_for_network_type_and_peering_policy_if_invalid():
    app = build_app()
    processor = importers.process_asn_data(processing_date, TestLookup(), app)
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

    processor = importers.process_asn_data(
        processing_date, TestLookup(default_country="AU"), app
    )
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
    processor = importers.process_asn_data(processing_date, TestLookup(), app)
    processor([data_with_problems])

    asns = app.get_all_asns()
    assert len(asns) == 0


def test_uses_registration_country_at_processing_date():
    updated_date = processing_date.replace(year=(processing_date.year - 1))

    class DateSensitiveLookup(ASNGeoLookup):
        __test__ = False

        def __init__(
            self, default_status: str = "assigned", default_country: str = "US"
        ):
            self.default_status = default_status
            self.default_country = default_country

        def get_iso2_country(self, asn: int, as_at: datetime) -> str:
            if as_at.year == updated_date.year:
                return "FR"
            return self.default_country

        def get_status(self, asn: int, as_at: datetime) -> str:
            assert as_at <= datetime.now(timezone.utc)
            assert asn > 0
            return self.default_status

        def get_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
            return []

        def get_routed_asns_for_country(
            self, country: str, as_at: datetime
        ) -> list[int]:
            return []

    app = build_app()
    processor = importers.process_asn_data(processing_date, DateSensitiveLookup(), app)
    processor([PeeringASNFactory(updated_date=updated_date)])

    asns = app.get_all_asns()
    asn_added = asns[0]
    assert asn_added.country_code == "US"
