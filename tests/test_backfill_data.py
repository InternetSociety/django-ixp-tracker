import json
from datetime import datetime
import re

import pytest
import responses

from ixp_tracker.conf import DATA_ARCHIVE_URL
from ixp_tracker.importers import import_data
from ixp_tracker.management.commands.ixp_tracker_import import DefaultASNGeoLookup
from ixp_tracker.models import ASN, IXP, IXPMember

pytestmark = pytest.mark.django_db


def test_with_no_data_returned_does_nothing():
    backfill_date = datetime(year=2024, month=1, day=1)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body=json.dumps({"ix": {"data": []}, "net": {"data": []}, "netixlan": {"data": []}}),
        )
        import_data(DefaultASNGeoLookup(), False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_handles_malformed_archives():
    backfill_date = datetime(year=2024, month=1, day=1)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body=json.dumps({}),
        )
        import_data(DefaultASNGeoLookup(), False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_handles_single_quoted_json():
    backfill_date = datetime(year=2024, month=1, day=1)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body="{'ix': {'data': []}, 'net': {'data': []}, 'netixlan': {'data': []}}",
        )
        import_data(DefaultASNGeoLookup(), False, backfill_date)

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
        import_data(DefaultASNGeoLookup(), False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 0

    asns = ASN.objects.all()
    assert len(asns) == 0

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_adds_all_data():
    backfill_date = datetime(year=2024, month=1, day=1)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(year=backfill_date.year, month=backfill_date.month, day=backfill_date.day),
            body=json.dumps(
                {
                    "ix":
                        {
                            "data":
                                [
                                    {
                                        "id": 1,
                                        "name": "City IX",
                                        "name_long": "City Internet Exchange Point",
                                        "city": "City",
                                        "country": "AF",
                                        "website": "http://example.com",
                                        "created": "2019-08-24T14:15:22Z",
                                        "updated": "2019-08-24T14:15:22Z",
                                    }
                                ]
                        },
                    "net":
                        {
                            "data":
                                [
                                    {
                                        "id": 3,
                                        "asn": 6543,
                                        "name": "New ASN",
                                        "info_type": "non-profit",
                                        "created": "2019-08-24T14:15:22Z",
                                        "updated": "2019-08-24T14:15:22Z",
                                    }

                                ]
                        },
                    "netixlan":
                        {
                            "data":
                                [
                                    {
                                        "asn": 6543,
                                        "ix_id": 1,
                                        "created": "2019-08-24T14:15:22Z",
                                        "updated": "2019-08-24T14:15:22Z",
                                        "is_rs_peer": True,
                                        "speed": 10000,
                                    }
                                ]
                        }
                }
            ),
        )
        import_data(DefaultASNGeoLookup(), False, backfill_date)

    ixps = IXP.objects.all()
    assert len(ixps) == 1

    asns = ASN.objects.all()
    assert len(asns) == 1

    members = IXPMember.objects.all()
    assert len(members) == 1
