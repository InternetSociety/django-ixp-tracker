from datetime import datetime, timezone
import pytest
from faker import Faker

from ixp_tracker.data_lookup import ASNGeoLookup
from ixp_tracker.event_store import (
    EventStorePersistence,
    EventStore,
    DjangoEventStore,
)
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    MemberImportData,
)
from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP
from ixp_tracker.ixp_tracker_projections import ASNList, IXPIdMapProjection
from tests.fixtures import (
    create_ixp,
    create_asn,
    MemoryEventStore,
    create_member,
    TestLookup,
)

pytestmark = pytest.mark.django_db

date_now = datetime.now(timezone.utc)


def test_imports_member(faker: Faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn = create_asn(faker, es)
    ixp = create_ixp(faker, es)

    assert len(ixp.get_members()) == 0

    imported = app.import_members(
        ixp, [create_member_import_data(faker, asn.number)], date_now
    )

    members = imported.get_members()
    assert len(members) == 1
    assert asn.number in members.keys()


def test_imports_multiple_members(faker: Faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn1 = create_asn(faker, es)
    asn2 = create_asn(faker, es)
    ixp = create_ixp(faker, es)

    assert len(ixp.get_members()) == 0

    imported = app.import_members(
        ixp,
        [
            create_member_import_data(faker, asn1.number),
            create_member_import_data(faker, asn2.number),
        ],
        date_now,
    )

    members = imported.get_members().keys()
    assert len(members) == 2
    assert asn1.number in members
    assert asn2.number in members


def test_adds_new_membership_for_existing_member_marked_as_left(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    membership_properties = {
        "start_date": datetime(year=2018, month=1, day=3),
        "end_date": datetime(year=2018, month=7, day=13, tzinfo=timezone.utc),
    }
    create_member(faker, es, ixp, asn, membership_properties)
    member_import_data = create_member_import_data(faker, asn.number)

    ixp = app.import_members(ixp, [member_import_data], date_now)

    updated = ixp.get_members().get(asn.number)
    assert updated.date_joined > membership_properties["end_date"]


def test_extends_membership_for_member_marked_as_left_if_created_before_date_left(
    faker,
):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    membership_properties = {
        "start_date": datetime(year=2018, month=1, day=3, tzinfo=timezone.utc),
        "end_date": datetime(year=2018, month=7, day=13, tzinfo=timezone.utc),
    }
    create_member(faker, es, ixp, asn, membership_properties)
    member_import_data = create_member_import_data(
        faker,
        asn.number,
        created_date=datetime(year=2018, month=6, day=18, tzinfo=timezone.utc),
    )

    ixp = app.import_members(ixp, [member_import_data], date_now)

    updated = ixp.get_members().get(asn.number)
    assert updated.date_joined == membership_properties["start_date"]
    assert updated.date_left is None


def test_ensure_multiple_member_entries_does_not_trigger_multiple_new_memberships(
    faker,
):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    membership_properties = {
        "start_date": datetime(year=2023, month=1, day=13, tzinfo=timezone.utc),
        "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc),
    }
    create_member(faker, es, ixp, asn, membership_properties)

    date_after_date_left = datetime(2023, 9, 24, tzinfo=timezone.utc)
    member_data_with_created_date_after_date_left = create_member_import_data(
        faker, asn.number, created_date=date_after_date_left
    )

    ixp = app.import_members(
        ixp,
        [
            member_data_with_created_date_after_date_left,
            member_data_with_created_date_after_date_left,
        ],
        date_now,
    )

    assert len(ixp.get_members()) == 1


def test_do_not_add_new_membership_for_same_created_date(faker):
    created_date = datetime(year=2023, month=1, day=13, tzinfo=timezone.utc)

    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    membership_properties = {
        "start_date": created_date,
        "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc),
    }
    create_member(faker, es, ixp, asn, membership_properties)

    # As we always create a new membership record if the most recent one has ended, for multiple ASN-IX combos this
    # could result in multiple new memberships being created
    member_import = create_member_import_data(
        faker, asn.number, created_date=created_date
    )

    ixp = app.import_members(ixp, [member_import], date_now)

    assert len(ixp.get_members()) == 1


def test_marks_ixp_active_if_has_three_members(
    faker,
):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es)
    member_import_data = []
    for _ in range(1, 4):
        asn = create_asn(faker, es)
        member_import_data.append(create_member_import_data(faker, asn.number))

    assert ixp.active_status is False

    ixp = app.import_members(ixp, member_import_data, date_now)

    assert ixp.active_status is True


def test_marks_ixp_inactive_if_members_drops_below_three(
    faker,
):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    ixp = create_ixp(faker, es, True)
    member_import_data = []
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
        if member_count < 3:
            # But only 2 existing members in the new import
            member_import_data.append(create_member_import_data(faker, asn.number))

    assert ixp.active_status is True

    ixp = app.import_members(ixp, member_import_data, date_now)

    assert ixp.active_status is False


def test_member_marked_left_due_to_zz_country_registration_is_not_imported(faker):
    mes = MemoryEventStore()
    app, es = build_app(
        mes, TestLookup(default_country="ZZ", default_status="reserved")
    )
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    membership_properties = {
        "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc),
    }
    create_member(faker, es, ixp, asn, membership_properties)
    member_import_data = create_member_import_data(faker, asn.number)

    sequence_before_import = ixp.sequence
    imported_member = ixp.get_members(True)[asn.number]

    ixp = app.import_members(ixp, [member_import_data], date_now)

    updated_member = ixp.get_members(True)[asn.number]
    # date_left should not be updated in this case
    assert updated_member.date_left == imported_member.date_left
    # no extra events should have been added
    assert ixp.sequence == sequence_before_import


def test_as112_is_marked_as_rejoined(faker):
    # Normally an AS with country ZZ that has been marked as left would be ignored
    # But we want AS112 to be considered in this case as it probably means it has left and rejoined
    mes = MemoryEventStore()
    app, es = build_app(
        mes, TestLookup(default_country="ZZ", default_status="reserved")
    )
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es, asn=112)
    membership_properties = {
        "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc),
    }
    create_member(faker, es, ixp, asn, membership_properties)
    member_import_data = create_member_import_data(faker, asn.number)

    ixp = app.import_members(ixp, [member_import_data], date_now)

    updated_member = ixp.get_members(True)[asn.number]
    assert updated_member.date_left is None


def build_app(
    es_db: EventStorePersistence | None = None,
    geo_lookup: ASNGeoLookup | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    app = IXPTracker(es, geo_lookup or TestLookup(default_country="US"))
    return app, es


def create_member_import_data(
    faker, asn: int, created_date: datetime | None = None
) -> MemberImportData:
    return {
        "asn": asn,
        "created_date": created_date
        or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        "updated_date": faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        "is_rs_peer": faker.boolean(),
        "port_speed": faker.random_number(digits=5),
    }
