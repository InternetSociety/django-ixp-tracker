from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP, ASN
from tests.fixtures import MemoryEventStore, create_asn


def test_snapshot_asns(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es)

    es.save_snapshot(asn)

    snapshot = es.load_snapshot(asn.id, ASN)

    assert snapshot.name == asn.name
    assert snapshot.number == asn.number
    assert snapshot.peeringdb_id == asn.peeringdb_id
    assert snapshot.network_type == asn.network_type
    assert snapshot.peering_policy == asn.peering_policy
    assert snapshot.country_code == asn.country_code
    assert snapshot.nro_status == asn.nro_status
    assert snapshot.is_routed == asn.is_routed
    assert snapshot.customer_asns == asn.customer_asns
