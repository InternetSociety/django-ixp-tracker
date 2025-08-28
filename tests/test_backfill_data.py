import json
from datetime import datetime, timezone
import re

import pytest
import responses

from ixp_tracker.conf import DATA_ARCHIVE_URL
from ixp_tracker.importers import import_data
from ixp_tracker.management.commands.ixp_tracker_import import DefaultAdditionalDataSources
from ixp_tracker.models import ASN, IXP, IXPMember

from .fixtures import PeeringASNFactory, PeeringIXFactory, PeeringNetIXLANFactory

pytestmark = pytest.mark.django_db
additional_data = DefaultAdditionalDataSources()


def test_with_no_data_returned_does_nothing():
    backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body=json.dumps({"ix": {"data": []}, "net": {"data": []}, "netixlan": {"data": []}}),
        )
        import_data(additional_data, False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_handles_malformed_archives():
    backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body=json.dumps({}),
        )
        import_data(additional_data, False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_handles_single_quoted_json():
    backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body="{'ix': {'data': []}, 'net': {'data': []}, 'netixlan': {'data': []}}",
        )
        import_data(additional_data, False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_queries_for_every_day_of_month():
    backfill_date = datetime(year=2024, month=1, day=1)
    with responses.RequestsMock() as rsps:
        data_url = DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day)
        data_url = data_url.replace("01.json", r'[0-9]{2}\.json')
        rsps.get(
            url=re.compile(data_url),
            status=404,
        )
        import_data(additional_data, False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_adds_all_data():
    backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
    asn_data = PeeringASNFactory()
    ix_data = PeeringIXFactory()
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body=json.dumps(
                {
                    "ix": {"data": [ix_data]},
                    "net": {"data": [asn_data]},
                    "netixlan": {"data": [PeeringNetIXLANFactory(asn=asn_data["asn"], ix_id=ix_data["id"])]}
                }
            ),
        )
        import_data(additional_data, False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 1

    asns = ASN.objects.all()
    assert len(asns) == 1

    members = IXPMember.objects.all()
    assert len(members) == 1
