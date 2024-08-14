import datetime
import json
from typing import List

import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker import importers


def noop_processor(data: List) -> bool:
    return True


def empty_list_processor(data: List) -> bool:
    assert len(data) == 0
    return True


def test_with_no_params_queries_peering_db_directly():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=json.dumps({"data": []}),
        )
        result = importers.get_data("/ix", empty_list_processor)
        assert result


def test_returns_false_if_query_fails():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            status=404
        )
        result = importers.get_data("/ix", noop_processor)
        assert result is False


def test_with_empty_response_passes_empty_list_to_processor():

    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=""
        )
        importers.get_data("/ix", empty_list_processor)


def test_imports_passes_data_to_processor():
    def list_processor(data: List) -> bool:
        assert len(data) == 1
        return True

    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix",
            body=json.dumps({"data": [{"foo": "bar"}]}),
        )
        importers.get_data("/ix", list_processor)


def test_with_limit_adds_query_params():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix?limit=200&skip=0",
            body=json.dumps({"data": []}),
        )
        importers.get_data("/ix", empty_list_processor, limit=200)


def test_requests_all_pages_until_empty_result():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix?limit=200&skip=0",
            body=json.dumps({"data": [{"foo": "bar"}]}),
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix?limit=200&skip=200",
            body=json.dumps({"data": []}),
        )
        importers.get_data("/ix", noop_processor, limit=200)


def test_queries_last_date_if_provided():
    def list_processor(data: List) -> bool:
        assert len(data) == 1
        return True

    last_updated = datetime.datetime(year=2024, month=5, day=1)
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix?updated__gte=2024-05-01",
            body=json.dumps({"data": [{"foo": "bar"}]}),
        )
        importers.get_data("/ix", list_processor, last_updated=last_updated)
