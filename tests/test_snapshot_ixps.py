from datetime import datetime, timezone, timedelta

from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker_aggregates import (
    IXP_TRACKER_EVENT_MAP,
    IXP,
    stringify_date,
    IXPMemberJoined,
)
from tests.fixtures import create_ixp, create_member, create_asn, MemoryEventStore


def test_snapshot_ixps(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    date_left = datetime.now(timezone.utc) - timedelta(days=2)
    ixp = create_member(faker, es, ixp, asn, {"end_date": date_left})
    # Ensure we have member history by the same AS rejoining
    date_rejoined = date_left + timedelta(days=1)
    ixp.member_joined(
        IXPMemberJoined(
            asn.number,
            stringify_date(date_rejoined),
            stringify_date(date_rejoined),
            stringify_date(date_rejoined),
            True,
            500,
        )
    )

    es.save_snapshot(ixp)

    snapshot = es.load_snapshot(ixp.id, IXP)

    assert snapshot == ixp
