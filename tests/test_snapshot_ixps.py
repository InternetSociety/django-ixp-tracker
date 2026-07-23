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

    assert snapshot.name == ixp.name
    assert snapshot.long_name == ixp.long_name
    assert snapshot.city == ixp.city
    assert snapshot.peeringdb_id == ixp.peeringdb_id
    assert snapshot.website == ixp.website
    assert snapshot.active_status == ixp.active_status
    assert snapshot.country_code == ixp.country_code
    assert snapshot.date_created == ixp.date_created
    assert snapshot.last_updated == ixp.last_updated
    assert snapshot.last_active == ixp.last_active
    assert snapshot.manrs_participant == ixp.manrs_participant
    assert snapshot.anchor_host == ixp.anchor_host
    assert snapshot.org_id == ixp.org_id
    assert snapshot.physical_locations == ixp.physical_locations
    assert snapshot.members == ixp.members
    assert snapshot.member_history == ixp.member_history
