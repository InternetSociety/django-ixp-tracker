import json
from datetime import datetime, timezone

import pytest
import responses

from ixp_tracker.conf import DATA_ARCHIVE_URL
from ixp_tracker.importers import import_data, build_app
from tests.fixtures import (
    MockLookup,
    PeeringASNFactory,
    PeeringIXFactory,
    PeeringNetIXLANFactory,
)

pytestmark = pytest.mark.django_db


def test_handles_malformed_archives(tmp_path):
    backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(
                year=backfill_date.year,
                month=backfill_date.month,
                day=backfill_date.day,
            ),
            body=json.dumps({}),
        )
        import_data(MockLookup(), backfill_date, local_archive_path=tmp_path)

    app = build_app()

    ixps = app.get_all_ixps()
    assert len(ixps) == 0


def test_adds_all_data(tmp_path):
    backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
    asn_data = PeeringASNFactory()
    asn_not_imported = PeeringASNFactory()
    ix_data = PeeringIXFactory()
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(
                year=backfill_date.year,
                month=backfill_date.month,
                day=backfill_date.day,
            ),
            body=json.dumps(
                {
                    "ix": {"data": [ix_data]},
                    "net": {"data": [asn_data, asn_not_imported]},
                    "netixlan": {
                        "data": [
                            PeeringNetIXLANFactory(
                                asn=asn_data["asn"], ix_id=ix_data["id"]
                            )
                        ]
                    },
                }
            ),
        )
        import_data(MockLookup(), backfill_date, local_archive_path=tmp_path)

    app = build_app()

    ixps = app.get_all_ixps()
    assert len(ixps) == 1

    ixp = ixps.pop()
    members = ixp.get_members()
    assert len(members.keys()) == 1

    asns = app.get_all_asns()
    assert len(asns) == 1
