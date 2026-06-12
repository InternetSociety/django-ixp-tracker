from datetime import datetime, timezone

from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP, IXP
from tests.fixtures import create_ixp, create_member, create_asn, MemoryEventStore


def test_snapshot_ixps(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    ixp = create_member(faker, es, ixp, asn, {"end_date": datetime.now(timezone.utc)})

    es.save_snapshot(ixp)

    snapshot = es.load_snapshot(ixp.id, IXP)

    assert snapshot == ixp
