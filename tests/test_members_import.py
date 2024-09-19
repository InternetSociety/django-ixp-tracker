from datetime import datetime, timedelta, timezone
import dateutil.parser

import pytest

from ixp_tracker import importers
from ixp_tracker.importers import ASNGeoLookup, dedupe_member_data
from ixp_tracker.models import ASN, IXP, IXPMember, IXPMembershipRecord

pytestmark = pytest.mark.django_db

dummy_member_data = {
    "asn": 12345,
    "ix_id": 2,
    "created": "2019-08-24T14:15:22Z",
    "updated": "2019-08-24T14:15:22Z",
    "is_rs_peer": True,
    "speed": 10000,
}

multiple_member_data = [
    {
        "asn": 56789,
        "ix_id": 5,
        "created": "2019-08-24T14:15:22Z",
        "updated": "2019-08-24T14:15:22Z",
        "is_rs_peer": False,
        "speed": 10000,
    },
    {
        "asn": 56789,
        "ix_id": 5,
        "created": "2018-08-24T14:15:22Z",
        "updated": "2018-08-24T14:15:22Z",
        "is_rs_peer": True,
        "speed": 3000,
    },
    {
        "asn": 56789,
        "ix_id": 5,
        "created": "2020-08-24T14:15:22Z",
        "updated": "2020-08-24T14:15:22Z",
        "is_rs_peer": False,
        "speed": 4000,
    }
]

date_now = datetime.utcnow().replace(tzinfo=timezone.utc)

class TestLookup(ASNGeoLookup):

    def __init__(self, default_status: str = "assigned"):
        self.default_status = default_status

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        assert as_at <= datetime.utcnow().replace(tzinfo=timezone.utc)
        assert asn > 0
        return self.default_status


def test_with_no_data_does_nothing():
    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_adds_new_member():
    create_asn_fixture(dummy_member_data["asn"])
    create_ixp_fixture(dummy_member_data["ix_id"])

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=members.first())
    assert len(current_membership) == 1


def test_does_nothing_if_no_asn_found():
    create_ixp_fixture(dummy_member_data["ix_id"])

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_does_nothing_if_no_ixp_found():
    create_asn_fixture(dummy_member_data["asn"])

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    members = IXPMember.objects.all()
    assert len(members) == 0


def test_updates_existing_member():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime(year=2023, month=7, day=13)
    )
    member.save()

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    members = IXPMember.objects.all()
    assert len(members) == 1
    updated = members.first()
    assert updated.last_active.year > 2023


def test_updates_membership_for_existing_member():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime(year=2023, month=7, day=13)
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=datetime(year=2023, month=7, day=13).date(),
        is_rs_peer=False,
        speed=500
    )
    membership.save()

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    membership = IXPMembershipRecord.objects.filter(member=member)
    assert len(membership) == 1
    current_membership = membership.first()
    assert current_membership.is_rs_peer
    assert current_membership.speed == 10000


def test_adds_new_membership_for_existing_member_marked_as_left():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime(year=2023, month=7, day=13)
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=datetime(year=2018, month=1, day=3).date(),
        end_date=datetime(year=2018, month=7, day=13),
        is_rs_peer=False,
        speed=500
    )
    membership.save()

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    members = IXPMember.objects.all()
    assert len(members) == 1
    current_membership = IXPMembershipRecord.objects.filter(member=member).order_by("-start_date")
    assert len(current_membership) == 2
    assert current_membership.first().end_date is None


def test_marks_member_as_left_that_is_no_longer_active():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    first_day_of_month = datetime.utcnow().replace(day=1)
    last_day_of_last_month = (first_day_of_month - timedelta(days=1))
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=last_day_of_last_month
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        is_rs_peer=False,
        speed=500
    )
    membership.save()
    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None

    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime("%Y-%m-%d") == last_day_of_last_month.strftime("%Y-%m-%d")


def test_does_not_mark_member_as_left_if_asn_is_assigned():
    asn = create_asn_fixture(dummy_member_data["asn"], "ZZ")
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime.utcnow()
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        is_rs_peer=False,
        speed=500
    )
    membership.save()
    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None

    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None


def test_marks_member_as_left_if_asn_is_not_assigned():
    asn = create_asn_fixture(dummy_member_data["asn"], "ZZ")
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    first_day_of_month = datetime.utcnow().replace(day=1)
    last_day_of_last_month = (first_day_of_month - timedelta(days=1))
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime.utcnow()
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        is_rs_peer=False,
        speed=500
    )
    membership.save()
    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date is None

    processor = importers.process_member_data(date_now, TestLookup("available"))
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime("%Y-%m-%d") == last_day_of_last_month.strftime("%Y-%m-%d")


def test_does_not_mark_as_left_before_joining_date():
    asn = create_asn_fixture(dummy_member_data["asn"], "ZZ")
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    first_day_of_month = datetime.utcnow().replace(day=1)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime.utcnow()
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=first_day_of_month.date(),
        is_rs_peer=False,
        speed=500
    )
    membership.save()

    processor = importers.process_member_data(date_now, TestLookup("available"))
    processor([])

    current_membership = IXPMembershipRecord.objects.filter(member=member)
    assert current_membership.first().end_date.strftime("%Y-%m-%d") == first_day_of_month.strftime("%Y-%m-%d")


def test_ensure_multiple_member_entries_does_not_trigger_multiple_new_memberships():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime(year=2023, month=7, day=13)
    )
    member.save()
    # As we always create a new membership record if the most recent one has ended, for multiple ASN-IX combos this
    # could result in multiple new memberships being created
    membership = IXPMembershipRecord(
        member=member,
        start_date=datetime(year=2023, month=1, day=13),
        is_rs_peer=False,
        speed=500,
        end_date=datetime(year=2023, month=7, day=13)
    )
    membership.save()

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data, dummy_member_data])

    memberships = IXPMembershipRecord.objects.filter(member=member)
    assert len(memberships) == 2


def test_do_not_add_new_membership_for_same_created_date():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=dummy_member_data["updated"],
        last_active=datetime(year=2023, month=7, day=13)
    )
    member.save()
    # As we always create a new membership record if the most recent one has ended, for multiple ASN-IX combos this
    # could result in multiple new memberships being created
    membership = IXPMembershipRecord(
        member=member,
        start_date=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        is_rs_peer=False,
        speed=500,
        end_date=datetime(year=2023, month=7, day=13)
    )
    membership.save()

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    memberships = IXPMembershipRecord.objects.filter(member=member)
    assert len(memberships) == 1


def test_dedupes_member_data_before_processing():
    deduped_data = dedupe_member_data(multiple_member_data)

    assert len(deduped_data) == 1


def test_set_rs_peer_to_true_if_any_member_is_set_to_true():
    deduped_data = dedupe_member_data(multiple_member_data)

    deduped_member = deduped_data[0]
    assert deduped_member["is_rs_peer"]


def test_speed_for_deduped_members_is_sum_of_all_speeds():
    deduped_data = dedupe_member_data(multiple_member_data)

    deduped_member = deduped_data[0]
    assert deduped_member["speed"] == 17000


def create_asn_fixture(as_number: int, country: str = "CH"):
    asn = ASN.objects.filter(number=as_number)
    if len(asn) > 0:
        return asn.first()
    asn = ASN(
        name="Network Org",
        number=as_number,
        peeringdb_id=5,
        network_type="other",
        registration_country_code=country,
        created="2019-01-01",
        last_updated="2024-05-01"
    )
    asn.save()
    return asn


def create_ixp_fixture(peering_db_id: int, country = "MM"):
    ixp = IXP(
        name="Old name",
        long_name="Network Name",
        city="Aberdeen",
        website="",
        active_status=True,
        peeringdb_id=peering_db_id,
        country_code=country,
        created=datetime(year=2020,month=10,day=1),
        last_updated=datetime(year=2023,month=10,day=1),
        last_active=datetime(year=2024, month=4, day=1)
    )
    ixp.save()
    return ixp
