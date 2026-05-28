from datetime import datetime, timedelta, timezone

import pytest

from ixp_tracker import importers
from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore
from ixp_tracker.importers import ASNGeoLookup
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXP_TRACKER_EVENT_MAP,
    IXPIdMapProjection,
    ASNList,
    MemberMapProjection,
)
from ixp_tracker.models import IXPMember, IXPMembershipRecord
from tests.fixtures import (
    ASNFactory,
    IXPFactory,
    PeeringNetIXLANFactory,
    create_member_fixture,
    create_ixp,
    create_asn,
    create_member,
)

pytestmark = pytest.mark.django_db

date_now = datetime.now(timezone.utc)
date_yesterday = date_now - timedelta(days=1)


class TestLookup(ASNGeoLookup):
    __test__ = False

    def __init__(self, default_status: str = "assigned"):
        self.default_status = default_status

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        assert as_at <= datetime.now(timezone.utc)
        assert asn > 0
        return self.default_status


def test_with_no_data_does_nothing():
    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([])

    members = app.get_all_members()
    assert len(members) == 0


def test_adds_new_member(faker):
    app, es = build_app()
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    member_import = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    members = app.get_all_members()
    assert len(members) == 1
    member = members.pop(0)
    assert member.asn_id == asn.id


def test_does_nothing_if_no_asn_found(faker):
    app, es = build_app()
    ixp = create_ixp(faker, es)
    member_import = PeeringNetIXLANFactory(ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    members = app.get_all_members()
    assert len(members) == 0


def test_does_nothing_if_no_ixp_found(faker):
    app, es = build_app()
    asn = create_asn(faker, es)
    member_import = PeeringNetIXLANFactory(asn=asn.number)

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    members = app.get_all_members()
    assert len(members) == 0


def test_updates_existing_member(faker):
    app, es = build_app()
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)

    existing = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id)
    processor = importers.process_member_data(date_yesterday, TestLookup(), app)
    processor([existing])

    updates = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id)
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([updates])

    members = app.get_all_members()
    assert len(members) == 1
    updated = members.pop(0)
    assert updated.last_active > date_yesterday


def test_updates_membership_for_existing_member(faker):
    app, es = build_app()
    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)

    existing = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id, speed=500, is_rs_peer=False)
    processor = importers.process_member_data(date_yesterday, TestLookup(), app)
    processor([existing])

    updates = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id, speed=10000, is_rs_peer=True)
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([updates])

    members = app.get_all_members()
    assert len(members) == 1
    updated = members.pop(0)
    assert updated.port_speed == 10000
    assert updated.is_rs_peer


@pytest.mark.xfail
def test_adds_new_membership_for_existing_member_marked_as_left():
    ixp = IXPFactory()
    member = create_member_fixture(
        ixp,
        membership_properties={
            "start_date": datetime(year=2018, month=1, day=3),
            "end_date": datetime(year=2018, month=7, day=13, tzinfo=timezone.utc),
        },
    )
    member_import = PeeringNetIXLANFactory(
        asn=member.asn.number, ix_id=ixp.peeringdb_id
    )

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=member).order_by(
        "-start_date"
    )
    assert len(current_membership) == 2
    assert current_membership.first().end_date is None


@pytest.mark.xfail
def test_extends_membership_for_member_marked_as_left_if_created_before_date_left():
    ixp = IXPFactory()
    member = create_member_fixture(
        ixp,
        membership_properties={
            "start_date": datetime(year=2018, month=1, day=3),
            "end_date": datetime(year=2018, month=7, day=13, tzinfo=timezone.utc),
        },
    )
    member_data_with_created_date_before_date_left = PeeringNetIXLANFactory(
        asn=member.asn.number,
        ix_id=ixp.peeringdb_id,
        created_date=datetime(year=2018, month=6, day=18, tzinfo=timezone.utc),
    )

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_data_with_created_date_before_date_left])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=member).order_by(
        "-start_date"
    )
    assert len(current_membership) == 1
    assert current_membership.first().end_date is None


@pytest.mark.xfail
def test_marks_member_as_left_that_is_no_longer_active():
    first_day_of_month = datetime.now(timezone.utc).replace(day=1)
    last_day_of_last_month = first_day_of_month - timedelta(days=1)
    date_more_than_month_ago = last_day_of_last_month - timedelta(days=17)

    ixp = IXPFactory()
    member = create_member_fixture(
        ixp,
        membership_properties={"start_date": date_more_than_month_ago},
        member_properties={"last_active": date_more_than_month_ago},
    )

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime(
        "%Y-%m-%d"
    ) == last_day_of_last_month.strftime("%Y-%m-%d")


@pytest.mark.xfail
def test_does_not_mark_member_as_left_if_asn_is_registered_in_country_zz_and_is_assigned():
    asn = ASNFactory(registration_country_code="ZZ")
    ixp = IXPFactory()
    member = create_member_fixture(
        ixp, asn, member_properties={"last_active": datetime.now(timezone.utc)}
    )

    app, _ = build_app()
    processor = importers.process_member_data(
        date_now, TestLookup(default_status="assigned"), app
    )
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None


@pytest.mark.xfail
def test_marks_member_as_left_if_asn_is_registered_in_country_zz_and_is_not_assigned():
    first_day_of_month = datetime.now(timezone.utc).replace(day=1)
    last_day_of_last_month = first_day_of_month - timedelta(days=1)

    asn = ASNFactory(registration_country_code="ZZ")
    ixp = IXPFactory()
    member = create_member_fixture(
        ixp, asn, member_properties={"last_active": datetime.now(timezone.utc)}
    )

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup("available"), app)
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime(
        "%Y-%m-%d"
    ) == last_day_of_last_month.strftime("%Y-%m-%d")


@pytest.mark.xfail
def test_does_not_mark_as_left_before_joining_date():
    first_day_of_month = datetime.now(timezone.utc).replace(day=1)

    asn = ASNFactory(registration_country_code="ZZ")
    ixp = IXPFactory()
    member = create_member_fixture(
        ixp,
        asn,
        member_properties={"last_active": datetime.now(timezone.utc)},
        membership_properties={"start_date": first_day_of_month},
    )

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup("available"), app)
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime(
        "%Y-%m-%d"
    ) == first_day_of_month.strftime("%Y-%m-%d")


@pytest.mark.xfail
def test_ensure_multiple_member_entries_does_not_trigger_multiple_new_memberships():
    ixp = IXPFactory()
    member = create_member_fixture(
        ixp,
        membership_properties={
            "start_date": datetime(year=2023, month=1, day=13, tzinfo=timezone.utc),
            "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc),
        },
    )

    date_after_date_left = datetime(2023, 9, 24, tzinfo=timezone.utc)
    member_data_with_created_date_after_date_left = PeeringNetIXLANFactory(
        created_date=date_after_date_left, ix_id=ixp.peeringdb_id, asn=member.asn.number
    )

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor(
        [
            member_data_with_created_date_after_date_left,
            member_data_with_created_date_after_date_left,
        ]
    )

    memberships = IXPMembershipRecord.objects.filter(member=member)
    assert len(memberships) == 2


@pytest.mark.xfail
def test_do_not_add_new_membership_for_same_created_date():
    ixp = IXPFactory()
    created_date = datetime(year=2023, month=1, day=13, tzinfo=timezone.utc)
    member = create_member_fixture(
        ixp,
        membership_properties={
            "start_date": created_date,
            "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc),
        },
    )
    # As we always create a new membership record if the most recent one has ended, for multiple ASN-IX combos this
    # could result in multiple new memberships being created
    member_import = PeeringNetIXLANFactory(
        created_date=created_date, ix_id=ixp.peeringdb_id, asn=member.asn.number
    )

    app, _ = build_app()
    processor = importers.process_member_data(date_now, TestLookup(), app)
    processor([member_import])

    memberships = IXPMembershipRecord.objects.filter(member=member)
    assert len(memberships) == 1


def build_app(es_db: EventStorePersistence = None) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    es.add_listener(MemberMapProjection())
    app = IXPTracker(es)
    return app, es
