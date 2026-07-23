from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP, ASN
from tests.fixtures import MemoryEventStore, create_asn


def test_snapshot_asns(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es)

    es.save_snapshot(asn)

    snapshot = es.load_snapshot(asn.id, ASN)

    assert snapshot == asn
