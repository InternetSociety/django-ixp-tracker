from datetime import datetime, timezone

import pytest

from ixp_tracker.importers import process_asn_data
from ixp_tracker.models import ASN

from .fixtures import ASNFactory, PeeringASNFactory

pytestmark = pytest.mark.django_db
processing_date = datetime.now(timezone.utc)


class TestLookup:
    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        assert as_at <= datetime.now(timezone.utc)
        assert asn > 0
        return "AU"

    def get_status(self, asn: int, as_at: datetime) -> str:
        return "assigned"


def test_with_empty_response_does_nothing():
    process_asn_data([], processing_date, TestLookup())

    asns = ASN.objects.all()
    assert len(asns) == 0


def test_imports_new_asn():
    process_asn_data([PeeringASNFactory()], processing_date, TestLookup())

    asns = ASN.objects.all()
    assert len(asns) == 1


def test_updates_existing_data():
    updated_asn_data = PeeringASNFactory()
    ASNFactory(
        number=updated_asn_data["asn"],
        peeringdb_id=updated_asn_data["id"],
        last_updated=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )

    process_asn_data([updated_asn_data], processing_date, TestLookup(), None)

    asns = ASN.objects.all()
    assert len(asns) == 1
    updated = asns.filter(peeringdb_id=updated_asn_data["id"]).first()
    assert updated.name == updated_asn_data["name"]
    assert updated.registration_country_code == "AU"


def test_handles_errors_with_source_data():
    data_with_problems = PeeringASNFactory()
    data_with_problems["updated"] = "abc"
    data_with_problems["asn"] = "foobar"

    process_asn_data([data_with_problems], processing_date, TestLookup())

    asns = ASN.objects.all()
    assert len(asns) == 0
