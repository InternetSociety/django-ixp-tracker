from datetime import datetime, timedelta, timezone

import pytest

from ixp_tracker import importers
from ixp_tracker.importers import ASNGeoLookup, dedupe_member_data
from ixp_tracker.models import IXPMember, IXPMembershipRecord
from tests.fixtures import ASNFactory, IXPFactory, PeeringNetIXLANFactory, create_member_fixture

pytestmark = pytest.mark.django_db

date_now = datetime.now(timezone.utc)

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
    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_adds_new_member():
    ixp = IXPFactory()
    asn = ASNFactory()
    member_import = PeeringNetIXLANFactory(asn=asn.number, ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=members.first())
    assert len(current_membership) == 1


def test_does_nothing_if_no_asn_found():
    ixp = IXPFactory()
    member_import = PeeringNetIXLANFactory(ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_does_nothing_if_no_ixp_found():
    asn = ASNFactory()
    member_import = PeeringNetIXLANFactory(asn=asn.number)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_updates_existing_member():
    ixp = IXPFactory()
    member = create_member_fixture(ixp)
    member_import = PeeringNetIXLANFactory(asn=member.asn.number, ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    members = IXPMember.objects.all()
    assert len(members) == 1
    updated = members.first()
    assert updated.last_active > member.last_active


def test_updates_membership_for_existing_member():
    ixp = IXPFactory()
    member = create_member_fixture(ixp, membership_properties={"speed": 500, "is_rs_peer": False})
    member_import = PeeringNetIXLANFactory(asn=member.asn.number, ix_id=ixp.peeringdb_id, speed=10000, is_rs_peer=True)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    membership = IXPMembershipRecord.objects.filter(member=member)
    assert len(membership) == 1
    current_membership = membership.first()
    assert current_membership.is_rs_peer
    assert current_membership.speed == 10000


def test_adds_new_membership_for_existing_member_marked_as_left():
    ixp = IXPFactory()
    member = create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2018, month=1, day=3), "end_date": datetime(year=2018, month=7, day=13, tzinfo=timezone.utc)})
    member_import = PeeringNetIXLANFactory(asn=member.asn.number, ix_id=ixp.peeringdb_id)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=member).order_by("-start_date")
    assert len(current_membership) == 2
    assert current_membership.first().end_date is None


def test_extends_membership_for_member_marked_as_left_if_created_before_date_left():
    ixp = IXPFactory()
    member = create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2018, month=1, day=3), "end_date": datetime(year=2018, month=7, day=13, tzinfo=timezone.utc)})
    member_data_with_created_date_before_date_left = PeeringNetIXLANFactory(asn=member.asn.number, ix_id=ixp.peeringdb_id, created_date=datetime(year=2018, month=6, day=18, tzinfo=timezone.utc))

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_data_with_created_date_before_date_left])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=member).order_by("-start_date")
    assert len(current_membership) == 1
    assert current_membership.first().end_date is None


def test_marks_member_as_left_that_is_no_longer_active():
    first_day_of_month = datetime.now(timezone.utc).replace(day=1)
    last_day_of_last_month = (first_day_of_month - timedelta(days=1))
    date_more_than_month_ago = last_day_of_last_month - timedelta(days=17)

    ixp = IXPFactory()
    member = create_member_fixture(ixp, membership_properties={"start_date": date_more_than_month_ago}, member_properties={"last_active": date_more_than_month_ago})

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None

    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime("%Y-%m-%d") == last_day_of_last_month.strftime("%Y-%m-%d")


def test_does_not_mark_member_as_left_if_asn_is_registered_in_country_zz_and_is_assigned():
    asn = ASNFactory(registration_country_code="ZZ")
    ixp = IXPFactory()
    member = create_member_fixture(ixp, asn, member_properties={"last_active": datetime.now(timezone.utc)})

    processor = importers.process_member_data(date_now, TestLookup(default_status="assigned"))
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None


def test_marks_member_as_left_if_asn_is_registered_in_country_zz_and_is_not_assigned():
    first_day_of_month = datetime.now(timezone.utc).replace(day=1)
    last_day_of_last_month = (first_day_of_month - timedelta(days=1))

    asn = ASNFactory(registration_country_code="ZZ")
    ixp = IXPFactory()
    member = create_member_fixture(ixp, asn, member_properties={"last_active": datetime.now(timezone.utc)})

    processor = importers.process_member_data(date_now, TestLookup("available"))
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime("%Y-%m-%d") == last_day_of_last_month.strftime("%Y-%m-%d")


def test_does_not_mark_as_left_before_joining_date():
    first_day_of_month = datetime.now(timezone.utc).replace(day=1)

    asn = ASNFactory(registration_country_code="ZZ")
    ixp = IXPFactory()
    member = create_member_fixture(ixp, asn, member_properties={"last_active": datetime.now(timezone.utc)}, membership_properties={"start_date": first_day_of_month})

    processor = importers.process_member_data(date_now, TestLookup("available"))
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime("%Y-%m-%d") == first_day_of_month.strftime("%Y-%m-%d")


def test_ensure_multiple_member_entries_does_not_trigger_multiple_new_memberships():
    ixp = IXPFactory()
    member = create_member_fixture(ixp, membership_properties={"start_date": datetime(year=2023, month=1, day=13, tzinfo=timezone.utc), "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc)})

    date_after_date_left = datetime(2023, 9, 24, tzinfo=timezone.utc)
    member_data_with_created_date_after_date_left = PeeringNetIXLANFactory(created_date=date_after_date_left, ix_id=ixp.peeringdb_id, asn=member.asn.number)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_data_with_created_date_after_date_left, member_data_with_created_date_after_date_left])

    memberships = IXPMembershipRecord.objects.filter(member=member)
    assert len(memberships) == 2


def test_do_not_add_new_membership_for_same_created_date():
    ixp = IXPFactory()
    created_date = datetime(year=2023, month=1, day=13, tzinfo=timezone.utc)
    member = create_member_fixture(ixp, membership_properties={"start_date": created_date, "end_date": datetime(year=2023, month=7, day=13, tzinfo=timezone.utc)})
    # As we always create a new membership record if the most recent one has ended, for multiple ASN-IX combos this
    # could result in multiple new memberships being created
    member_import = PeeringNetIXLANFactory(created_date=created_date, ix_id=ixp.peeringdb_id, asn=member.asn.number)

    processor = importers.process_member_data(date_now, TestLookup())
    processor([member_import])

    memberships = IXPMembershipRecord.objects.filter(member=member)
    assert len(memberships) == 1


def test_deduplicates_member_data_before_processing():
    member_import = PeeringNetIXLANFactory()
    duplicate_one = PeeringNetIXLANFactory(ix_id=member_import["ix_id"], asn=member_import["asn"])
    duplicate_two = PeeringNetIXLANFactory(ix_id=member_import["ix_id"], asn=member_import["asn"])

    deduplicated_data = dedupe_member_data([member_import, duplicate_one, duplicate_two])

    assert len(deduplicated_data) == 1


def test_set_rs_peer_to_true_if_any_member_is_set_to_true():
    member_import = PeeringNetIXLANFactory(is_rs_peer=False)
    duplicate_one = PeeringNetIXLANFactory(ix_id=member_import["ix_id"], asn=member_import["asn"], is_rs_peer=True)
    duplicate_two = PeeringNetIXLANFactory(ix_id=member_import["ix_id"], asn=member_import["asn"], is_rs_peer=False)

    deduplicated_data = dedupe_member_data([member_import, duplicate_one, duplicate_two])

    deduplicated_member = deduplicated_data[0]
    assert deduplicated_member["is_rs_peer"]


def test_speed_for_deduped_members_is_sum_of_all_speeds():
    member_import = PeeringNetIXLANFactory(speed=500)
    duplicate_one = PeeringNetIXLANFactory(ix_id=member_import["ix_id"], asn=member_import["asn"], speed=1000)
    duplicate_two = PeeringNetIXLANFactory(ix_id=member_import["ix_id"], asn=member_import["asn"], speed=3000)

    deduplicated_data = dedupe_member_data([member_import, duplicate_one, duplicate_two])

    deduplicated_member = deduplicated_data[0]
    assert deduplicated_member["speed"] == 4500
