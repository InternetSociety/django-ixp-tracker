from datetime import datetime, timezone

import pytest

from ixp_tracker.event_store import DjangoEventStore
from ixp_tracker.importers import process_member_data
from ixp_tracker.ixp_tracker_aggregates import IXP
from tests.fixtures import (
    PeeringNetIXLANFactory,
    MockLookup,
    create_ixp,
    create_asn,
    create_member,
    build_app,
)

pytestmark = pytest.mark.django_db

date_now = datetime.now(timezone.utc)


def test_adds_new_members(faker):
    app, es = build_app()
    app.time_travel(date_now)

    ixp = create_ixp(faker, es)
    asn_one = create_asn(faker, es)
    asn_two = create_asn(faker, es)
    member_import_one = PeeringNetIXLANFactory(
        asn=asn_one.number, ix_id=ixp.peeringdb_id
    )
    member_import_two = PeeringNetIXLANFactory(
        asn=asn_two.number, ix_id=ixp.peeringdb_id
    )

    process_member_data(
        [member_import_one, member_import_two], date_now, MockLookup(), app
    )

    ixp = es.get_aggregate(ixp.id, IXP)
    members = ixp.get_members()
    assert len(members) == 2
    assert asn_one.number in members.keys()
    assert asn_two.number in members.keys()


def test_does_nothing_if_no_asn_found(faker):
    des = DjangoEventStore()
    app, es = build_app(des)
    app.time_travel(date_now)

    ixp = create_ixp(faker, es)
    member_import = PeeringNetIXLANFactory(ix_id=ixp.peeringdb_id)
    fixture_events = len(des.get_events())

    process_member_data([member_import], date_now, MockLookup(), app)

    assert len(des.get_events()) == fixture_events


def test_does_nothing_if_no_ixp_found(faker):
    des = DjangoEventStore()
    app, es = build_app(des)
    app.time_travel(date_now)

    asn = create_asn(faker, es)
    member_import = PeeringNetIXLANFactory(asn=asn.number)
    fixture_events = len(des.get_events())

    app, _ = build_app()
    process_member_data([member_import], date_now, MockLookup(), app)

    assert len(des.get_events()) == fixture_events


def test_updates_member(faker):
    app, es = build_app()
    app.time_travel(date_now)

    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    create_member(faker, es, ixp, asn, {"speed": 500, "is_rs_peer": False})
    member_import = PeeringNetIXLANFactory(
        asn=asn.number, ix_id=ixp.peeringdb_id, speed=10000, is_rs_peer=True
    )
    last_active = ixp.get_members().get(asn.number).last_active

    process_member_data([member_import], date_now, MockLookup(), app)

    ixp = es.get_aggregate(ixp.id, IXP)
    updated = ixp.get_members().get(asn.number)
    assert updated.is_rs_peer
    assert updated.port_speed == 10000
    assert updated.last_active > last_active


def test_marks_members_left_if_ixp_not_referenced_in_import(faker):
    app, es = build_app()
    app.time_travel(date_now)

    ixp = create_ixp(faker, es, True)
    # Create 3 existing members
    for member_count in range(1, 4):
        asn = create_asn(faker, es)
        create_member(
            faker,
            es,
            ixp,
            asn,
            {"last_active": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc)},
        )
    assert ixp.active_status is True

    process_member_data([], date_now, MockLookup(), app)

    ixp = es.get_aggregate(ixp.id, IXP)
    active_members = ixp.get_members()
    assert len(active_members) == 0
    all_members = ixp.get_members(True)
    assert len(all_members) == 3
    assert ixp.active_status is False
