from datetime import datetime, timezone

import pytest
import responses
from faker import Faker

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers
from ixp_tracker.ixp_tracker_aggregates import NetworkType, PeeringPolicy

from .fixtures import PeeringASNFactory, build_app, MockLookup

pytestmark = pytest.mark.django_db
processing_date = datetime.now(timezone.utc)


def test_with_empty_response_does_nothing():
    app, _ = build_app()
    processor = importers.process_asn_data(processing_date, MockLookup(), app)
    processor([])

    asns = app.get_all_asns()
    assert len(asns) == 0


def test_with_no_existing_data_gets_all_data():
    with responses.RequestsMock() as rsps:
        app, _ = build_app()
        rsps.get(url=IXP_TRACKER_PEERING_DB_URL + "/net?limit=200&skip=0", body="")
        importers.import_asns(processing_date, MockLookup(), False, es_app=app)

        asns = app.get_all_asns()
        assert len(asns) == 0


def test_imports_new_asn(faker: Faker):
    app, _ = build_app()
    data_to_import = PeeringASNFactory()
    customer_asns = faker.pylist(
        nb_elements=10, variable_nb_elements=True, value_types=[int]
    )
    processor = importers.process_asn_data(
        processing_date,
        MockLookup(routed_asns=[data_to_import["asn"]], customer_asns=customer_asns),
        app,
    )
    processor([data_to_import])

    asns = app.get_all_asns()
    assert len(asns) == 1
    as_entity = asns[0]
    assert as_entity.is_routed
    assert as_entity.customer_asns == customer_asns


def test_uses_defaults_for_network_type_and_peering_policy_if_invalid():
    app, _ = build_app()
    processor = importers.process_asn_data(processing_date, MockLookup(), app)
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
    app, _ = build_app()
    app.import_asn(
        updated_asn_data["asn"],
        name,
        NetworkType.CONTENT,
        PeeringPolicy.OPEN,
        updated_asn_data["id"],
        faker.country_code(),
        faker.pybool(),
        faker.pylist(nb_elements=10, variable_nb_elements=True, value_types=[int]),
    )

    processor = importers.process_asn_data(
        processing_date, MockLookup(default_country="AU"), app
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

    app, _ = build_app()
    processor = importers.process_asn_data(processing_date, MockLookup(), app)
    processor([data_with_problems])

    asns = app.get_all_asns()
    assert len(asns) == 0


def test_uses_registration_country_at_processing_date():
    updated_date = processing_date.replace(year=(processing_date.year - 1))

    class DateSensitiveLookup(MockLookup):
        def get_iso2_country(self, asn: int, as_at: datetime) -> str:
            if as_at.year == updated_date.year:
                return "FR"
            return self.default_country

    app, _ = build_app()
    processor = importers.process_asn_data(processing_date, DateSensitiveLookup(), app)
    processor([PeeringASNFactory(updated_date=updated_date)])

    asns = app.get_all_asns()
    asn_added = asns[0]
    assert asn_added.country_code == "US"
