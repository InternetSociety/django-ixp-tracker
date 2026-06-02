from datetime import datetime, timezone

import pytest

from ixp_tracker import importers
from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXP_TRACKER_EVENT_MAP,
    IXPIdMapProjection,
    ASNList,
    IXP,
)
from tests.fixtures import (
    PeeringNetIXLANFactory,
    TestLookup,
    create_ixp,
    create_asn,
    create_member,
)

pytestmark = pytest.mark.django_db

date_now = datetime.now(timezone.utc)


def test_adds_new_member(faker):
    app, es = build_app()
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    member_import = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    ixp = es.get_aggregate(ixp.id, IXP)
    members = ixp.get_members()
    assert len(members) == 1
    assert asn.number in members.keys()


def test_does_nothing_if_no_asn_found(faker):
    des = DjangoEventStore()
    app, es = build_app(des)
    ixp = create_ixp(faker, es)
    member_import = PeeringNetIXLANFactory(ix_id=ixp.peeringdb_id)
    fixture_events = len(des.get_events())

    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    assert len(des.get_events()) == fixture_events


def test_does_nothing_if_no_ixp_found(faker):
    des = DjangoEventStore()
    app, es = build_app(des)
    asn = create_asn(faker, es)
    member_import = PeeringNetIXLANFactory(asn=asn.number)
    fixture_events = len(des.get_events())

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    assert len(des.get_events()) == fixture_events


def test_updates_member(faker):
    app, es = build_app()
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    create_member(faker, es, ixp, asn, {"speed": 500, "is_rs_peer": False})
    member_import = PeeringNetIXLANFactory(
        asn=asn.number, ix_id=ixp.peeringdb_id, speed=10000, is_rs_peer=True
    )
    last_active = ixp.get_members().get(asn.number).last_active

    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    ixp = es.get_aggregate(ixp.id, IXP)
    updated = ixp.get_members().get(asn.number)
    assert updated.is_rs_peer
    assert updated.port_speed == 10000
    assert updated.last_active > last_active


def build_app(
    es_db: EventStorePersistence | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    app = IXPTracker(es, TestLookup())
    return app, es
