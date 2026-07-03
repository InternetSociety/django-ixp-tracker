import responses

from django_test_app.settings import IXP_TRACKER_PEERING_DB_URL
from ixp_tracker.gather_data import gather_data


def test_gathers_all_data_types():
    with responses.RequestsMock() as rsps:
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/as_set", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/campus", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/carrier", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/carrierfac",
            body='{"data":[{"foo":"bar"}]}',
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/fac", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ix", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ixfac", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ixlan", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/ixpfx", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/net", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/netfac", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/netixlan",
            body='{"data":[{"foo":"bar"}]}',
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/org", body='{"data":[{"foo":"bar"}]}'
        )
        rsps.get(
            url=IXP_TRACKER_PEERING_DB_URL + "/poc",
            body='{"data":[{"foo":"bar", "visible": "Public"},{"foo":"bar", "visible": "Users"},{"foo":"bar", "visible": "baz"}]}',
        )

        all_data = gather_data()

        assert len(all_data["as_set"]["data"]) > 0
        assert len(all_data["campus"]["data"]) > 0
        assert len(all_data["carrier"]["data"]) > 0
        assert len(all_data["carrierfac"]["data"]) > 0
        assert len(all_data["fac"]["data"]) > 0
        assert len(all_data["ix"]["data"]) > 0
        assert len(all_data["ixfac"]["data"]) > 0
        assert len(all_data["ixlan"]["data"]) > 0
        assert len(all_data["ixpfx"]["data"]) > 0
        assert len(all_data["net"]["data"]) > 0
        assert len(all_data["netfac"]["data"]) > 0
        assert len(all_data["netixlan"]["data"]) > 0
        assert len(all_data["org"]["data"]) > 0
        # Check we only get 1 POC as we need to filter on "visible: Public"
        assert len(all_data["poc"]["data"]) == 1
