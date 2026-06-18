from datetime import datetime, timezone, timedelta

from faker import Faker

from ixp_tracker.ixp_tracker_aggregates import (
    IXP_TRACKER_EVENT_MAP,
    IXPMemberLeft,
    stringify_date,
    IXPMemberJoined,
)

from ixp_tracker.event_store import EventStore

from tests.fixtures import create_ixp, create_member, MemoryEventStore, create_asn


def test_includes_historical_memberships(faker: Faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    # IXP with one member
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    start_date = datetime.now(timezone.utc) - timedelta(weeks=4)
    create_member(faker, es, ixp, asn, {"start_date": start_date})

    # Member leaves
    date_left = start_date + timedelta(weeks=1)
    ixp.member_left(IXPMemberLeft(asn.number, stringify_date(date_left)))

    # Member rejoins
    date_rejoined = date_left + timedelta(weeks=1)
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

    # Between start_date and date_left we should have one member
    members_at = ixp.get_members(as_at=(start_date + timedelta(days=3)))
    assert len(members_at.keys()) == 1

    # Between date_left and date_rejoined we should have no members
    members_at = ixp.get_members(as_at=(date_left + timedelta(days=3)))
    assert len(members_at.keys()) == 0

    # After date_rejoined we should have one member again
    members_at = ixp.get_members(as_at=(date_rejoined + timedelta(days=3)))
    assert len(members_at.keys()) == 1
