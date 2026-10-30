from ixp_tracker.get_atlas_anchor_hosts import get_atlas_anchor_hosts
from tests.fixtures import PeeringASNFactory, PeeringIXFactory


def test_returns_nothing_if_no_asns_provided():
    anchor_hosts = get_atlas_anchor_hosts([], [], [])

    assert len(anchor_hosts) == 0


def test_net_record_has_no_org():
    net_record = PeeringASNFactory(org_id=None)
    anchor_hosts = get_atlas_anchor_hosts([], [net_record], [net_record["asn"]])

    assert len(anchor_hosts) == 0


def test_net_record_org_has_no_ixp():
    net_record = PeeringASNFactory()
    anchor_hosts = get_atlas_anchor_hosts([], [net_record], [net_record["asn"]])

    assert len(anchor_hosts) == 0


def test_anchor_asn_has_matching_ixp():
    net_record = PeeringASNFactory()
    ixp_record = PeeringIXFactory(org_id=net_record["org_id"])
    anchor_hosts = get_atlas_anchor_hosts(
        [ixp_record], [net_record], [net_record["asn"]]
    )

    assert len(anchor_hosts) == 1
    assert ixp_record["id"] in anchor_hosts


def test_anchor_asn_org_matches_multiple_ixps():
    net_record = PeeringASNFactory()
    ixp_records = [
        PeeringIXFactory(org_id=net_record["org_id"]),
        PeeringIXFactory(org_id=net_record["org_id"]),
    ]
    anchor_hosts = get_atlas_anchor_hosts(
        ixp_records, [net_record], [net_record["asn"]]
    )

    assert len(anchor_hosts) == 2
    assert ixp_records[0]["id"] in anchor_hosts
    assert ixp_records[1]["id"] in anchor_hosts


def test_multiple_anchors_for_same_ixp_returns_ixp_once():
    net_one = PeeringASNFactory()
    net_two = PeeringASNFactory(org_id=net_one["org_id"])
    ixp_record = PeeringIXFactory(org_id=net_one["org_id"])

    anchor_hosts = get_atlas_anchor_hosts(
        [ixp_record], [net_one, net_two], [net_one["asn"], net_two["asn"]]
    )

    assert len(anchor_hosts) == 1
    assert ixp_record["id"] in anchor_hosts
