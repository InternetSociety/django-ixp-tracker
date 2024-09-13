import json
from datetime import datetime, timezone

import pytest
import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers
from ixp_tracker.models import ASN

pytestmark = pytest.mark.django_db

dummy_asn_data = {
    "id": 3,
    "asn": 6543,
    "name": "New ASN",
    "info_type": "non-profit",
    "created": "2019-08-24T14:15:22Z",
    "updated": "2019-08-24T14:15:22Z",
}


class TestLookup:

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        assert as_at <= datetime.utcnow().replace(tzinfo=timezone.utc)
        assert asn > 0
        return "AU"

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass


def test_with_empty_response_does_nothing():
    processor = importers.process_asn_data(TestLookup())
    processor([])

    asns = ASN.objects.all()
    assert len(asns) == 0


def test_with_no_existing_data_gets_all_data():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net?limit=200&skip=0",
            body=""
        )
        importers.import_asns(TestLookup(), False)

        asns = ASN.objects.all()
        assert len(asns) == 0


def test_imports_new_asn():
    processor = importers.process_asn_data(TestLookup())
    processor([dummy_asn_data])

    asns = ASN.objects.all()
    assert len(asns) == 1


def test_updates_existing_data():
    asn = ASN(
        name="Network Org",
        number=dummy_asn_data["asn"],
        peeringdb_id=dummy_asn_data["id"],
        network_type="other",
        registration_country_code="CH",
        created="2019-01-01",
        last_updated="2024-05-01"
    )
    asn.save()
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net?updated__gte=2024-05-01&limit=200&skip=0",
            body=json.dumps({"data": [dummy_asn_data]}),
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net?updated__gte=2024-05-01&limit=200&skip=200",
            body=json.dumps({"data": []}),
        )
        importers.import_asns(TestLookup(), False)

        asns = ASN.objects.all()
        assert len(asns) == 1
        updated = asns.filter(peeringdb_id=dummy_asn_data["id"]).first()
        assert updated.name == "New ASN"
        assert updated.registration_country_code == "AU"


def test_handles_errors_with_source_data():
    data_with_problems = dummy_asn_data
    data_with_problems["updated"] = "abc"
    data_with_problems["asn"] = "foobar"

    processor = importers.process_asn_data(TestLookup())
    processor([data_with_problems])

    asns = ASN.objects.all()
    assert len(asns) == 0
