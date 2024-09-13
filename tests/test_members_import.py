from datetime import datetime, timedelta, timezone
import dateutil.parser

import pytest

from ixp_tracker import importers
from ixp_tracker.models import ASN, IXP, IXPMember

pytestmark = pytest.mark.django_db

dummy_member_data = {
    "asn": 12345,
    "ix_id": 2,
    "created": "2019-08-24T14:15:22Z",
    "updated": "2019-08-24T14:15:22Z",
    "is_rs_peer": True,
    "speed": 10000,
}

date_now = datetime.utcnow().replace(tzinfo=timezone.utc)

class TestLookup:

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
        member_since=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        last_updated=dummy_member_data["updated"],
        is_rs_peer=False,
        speed=500,
        last_active=datetime(year=2023, month=7, day=13)
    )
    member.save()

    processor = importers.process_member_data(date_now, TestLookup())
    processor([dummy_member_data])

    members = IXPMember.objects.all()
    assert len(members) == 1
    updated = members.first()
    assert updated.is_rs_peer is True
    assert updated.speed == dummy_member_data["speed"]


def test_marks_member_as_left_that_is_no_longer_active():
    asn = create_asn_fixture(dummy_member_data["asn"])
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    first_day_of_month = datetime.utcnow().replace(day=1)
    last_day_of_last_month = (first_day_of_month - timedelta(days=1))
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        member_since=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        last_updated=dummy_member_data["updated"],
        is_rs_peer=False,
        speed=500,
        last_active=last_day_of_last_month
    )
    member.save()
    members = IXPMember.objects.all()
    assert members.first().date_left is None

    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    members = IXPMember.objects.all()
    assert members.first().date_left.strftime("%Y-%m-%d") == last_day_of_last_month.strftime("%Y-%m-%d")


def test_does_not_mark_member_as_left_if_asn_is_assigned():
    asn = create_asn_fixture(dummy_member_data["asn"], "ZZ")
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        member_since=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        last_updated=dummy_member_data["updated"],
        is_rs_peer=False,
        speed=500,
        last_active=datetime.utcnow()
    )
    member.save()
    members = IXPMember.objects.all()
    assert members.first().date_left is None

    processor = importers.process_member_data(date_now, TestLookup())
    processor([])

    members = IXPMember.objects.all()
    assert members.first().date_left is None


def test_marks_member_as_left_if_asn_is_not_assigned():
    asn = create_asn_fixture(dummy_member_data["asn"], "ZZ")
    ixp = create_ixp_fixture(dummy_member_data["ix_id"])
    first_day_of_month = datetime.utcnow().replace(day=1)
    last_day_of_last_month = (first_day_of_month - timedelta(days=1))
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        member_since=dateutil.parser.isoparse(dummy_member_data["created"]).date(),
        last_updated=dummy_member_data["updated"],
        is_rs_peer=False,
        speed=500,
        last_active=datetime.utcnow()
    )
    member.save()
    members = IXPMember.objects.all()
    assert members.first().date_left is None

    processor = importers.process_member_data(date_now, TestLookup("available"))
    processor([])

    members = IXPMember.objects.all()
    assert members.first().date_left.strftime("%Y-%m-%d") == last_day_of_last_month.strftime("%Y-%m-%d")


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
