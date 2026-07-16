import json
from datetime import datetime, timezone, timedelta
import re

import pytest
import responses

from ixp_tracker.conf import DATA_ARCHIVE_URL
from ixp_tracker.importers import get_archived_data

from .fixtures import PeeringIXFactory

pytestmark = pytest.mark.django_db
backfill_date = datetime(year=2024, month=1, day=1).replace(tzinfo=timezone.utc)
example_pdb_data = {
    "ix": {"data": [PeeringIXFactory()]},
    "net": {"data": []},
    "netixlan": {"data": []},
}


def test_handles_single_quoted_json(tmp_path):
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=DATA_ARCHIVE_URL.format(
                year=backfill_date.year,
                month=backfill_date.month,
                day=backfill_date.day,
            ),
            body="{'ix': {'data': []}, 'net': {'data': []}, 'netixlan': {'data': []}}",
        )
        archived_data = get_archived_data(backfill_date, tmp_path)

    ixps = archived_data.get("ix").get("data")
    assert len(ixps) == 0


def test_prefers_local_archived_data(tmp_path):
    file_name = f"{tmp_path}/{backfill_date.year}{backfill_date.month:02}{backfill_date.day:02}.peeringdb_2_dump.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ix": {"data": [PeeringIXFactory()]},
                "net": {"data": []},
                "netixlan": {"data": []},
            },
            f,
            ensure_ascii=False,
            indent=4,
        )
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        data_url = DATA_ARCHIVE_URL.format(
            year=backfill_date.year, month=backfill_date.month, day=backfill_date.day
        )
        caida = rsps.get(
            url=re.compile(data_url),
            status=404,
        )
        archived_data = get_archived_data(backfill_date, tmp_path)

        ixps = archived_data.get("ix").get("data")
        assert len(ixps) == 1
        assert caida.call_count == 0


def test_prefers_caida_on_right_date_over_older_data_locally(tmp_path):
    day_before_backfill = backfill_date - timedelta(days=1)
    file_name = f"{tmp_path}/{day_before_backfill.year}{day_before_backfill.month:02}{day_before_backfill.day:02}.peeringdb_2_dump.json"

    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(example_pdb_data, f, ensure_ascii=False, indent=4)
    with responses.RequestsMock() as rsps:
        data_url = DATA_ARCHIVE_URL.format(
            year=backfill_date.year, month=backfill_date.month, day=backfill_date.day
        )
        caida = rsps.get(
            url=re.compile(data_url),
            body=json.dumps(example_pdb_data),
        )
        archived_data = get_archived_data(backfill_date, tmp_path)

        ixps = archived_data.get("ix").get("data")
        assert len(ixps) == 1
        assert caida.call_count == 1


def test_gets_data_up_to_fifteen_days_old(tmp_path):
    fifteen_days_before_backfill = backfill_date - timedelta(days=15)
    with responses.RequestsMock() as rsps:
        caida_query_date = backfill_date
        while caida_query_date.date() > fifteen_days_before_backfill.date():
            data_url = DATA_ARCHIVE_URL.format(
                year=caida_query_date.year,
                month=caida_query_date.month,
                day=caida_query_date.day,
            )
            rsps.get(
                url=re.compile(data_url),
                status=404,
            )
            caida_query_date = caida_query_date - timedelta(days=1)
        data_url = DATA_ARCHIVE_URL.format(
            year=caida_query_date.year,
            month=caida_query_date.month,
            day=caida_query_date.day,
        )
        rsps.get(
            url=re.compile(data_url),
            body=json.dumps(example_pdb_data),
        )
        archived_data = get_archived_data(backfill_date, tmp_path)

        ixps = archived_data.get("ix").get("data")
        assert len(ixps) == 1


def test_with_no_data_up_to_fifteen_days_old_returns_nothing(tmp_path):
    fifteen_days_before_backfill = backfill_date - timedelta(days=15)
    with responses.RequestsMock() as rsps:
        caida_query_date = backfill_date
        while caida_query_date.date() >= fifteen_days_before_backfill.date():
            data_url = DATA_ARCHIVE_URL.format(
                year=caida_query_date.year,
                month=caida_query_date.month,
                day=caida_query_date.day,
            )
            rsps.get(
                url=re.compile(data_url),
                status=404,
            )
            caida_query_date = caida_query_date - timedelta(days=1)

        archived_data = get_archived_data(backfill_date, tmp_path)

        assert archived_data is None
