import json
from datetime import datetime, timezone

import pytest
import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers
from ixp_tracker.models import ASN

from .fixtures import ASNFactory, MockLookup, PeeringASNFactory

pytestmark = pytest.mark.django_db
processing_date = datetime.now(timezone.utc)



def test_with_empty_response_does_nothing():
    processor = importers.process_asn_data(processing_date, MockLookup())
    processor([])

    asns = ASN.objects.all()
    assert len(asns) == 0


def test_with_no_existing_data_gets_all_data():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net?limit=200&skip=0",
            body=""
        )
        importers.import_asns(processing_date, MockLookup(), False)

        asns = ASN.objects.all()
        assert len(asns) == 0


def test_imports_new_asn():
    processor = importers.process_asn_data(processing_date, MockLookup())
    processor([PeeringASNFactory()])

    asns = ASN.objects.all()
    assert len(asns) == 1


def test_updates_existing_data():
    updated_asn_data = PeeringASNFactory()
    ASNFactory(
        number=updated_asn_data["asn"],
        peeringdb_id=updated_asn_data["id"],
        last_updated=datetime(2024, 5, 1, tzinfo=timezone.utc)
    )
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net?updated__gte=2024-05-01&limit=200&skip=0",
            body=json.dumps({"data": [updated_asn_data]}),
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net?updated__gte=2024-05-01&limit=200&skip=200",
            body=json.dumps({"data": []}),
        )
        importers.import_asns(processing_date, MockLookup(), False)

        asns = ASN.objects.all()
        assert len(asns) == 1
        updated = asns.filter(peeringdb_id=updated_asn_data["id"]).first()
        assert updated.name == updated_asn_data["name"]
        assert updated.registration_country_code == "AU"


def test_handles_errors_with_source_data():
    data_with_problems = PeeringASNFactory()
    data_with_problems["updated"] = "abc"
    data_with_problems["asn"] = "foobar"

    processor = importers.process_asn_data(processing_date, MockLookup())
    processor([data_with_problems])

    asns = ASN.objects.all()
    assert len(asns) == 0


def test_adds_rpki_data():
    asn_to_import = PeeringASNFactory()
    summary_by_roa = {
        "v4": {
            "valid": 3,
            "invalid": 2,
            "unknown": 1,
        },
        "v6": {
            "valid": 7,
            "invalid": 5,
            "unknown": 4,
        },
    }
    summary_by_address = {
        "v4": {
            "valid": 31,
            "invalid": 22,
            "unknown": 16,
        },
        "v6": {
            "valid": 78,
            "invalid": 55,
            "unknown": 40,
        },
    }
    rpki_data = {
        "by_roa": summary_by_roa,
        "by_address": summary_by_address
    }
    data_lookup = MockLookup(rpki_data=rpki_data)

    processor = importers.process_asn_data(processing_date, data_lookup)
    processor([asn_to_import])

    asn = ASN.objects.first()
    assert asn.rpki_counts_by_roa == summary_by_roa
    assert asn.rpki_counts_by_address == summary_by_address
