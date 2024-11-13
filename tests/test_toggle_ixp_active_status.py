import pytest
from datetime import datetime, timedelta, timezone

from ixp_tracker.importers import toggle_ixp_active_status
from ixp_tracker.models import IXP, IXPMember, IXPMembershipRecord
from tests.fixtures import create_asn_fixture, create_ixp_fixture

pytestmark = pytest.mark.django_db
processing_date = datetime.utcnow().replace(tzinfo=timezone.utc)


def test_active_ixp_with_members_remains_active():
    ixp = create_ixp_fixture(1)
    asn = create_asn_fixture(12345)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=ixp.last_updated,
        last_active=ixp.last_active
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=ixp.created,
        is_rs_peer=True,
        speed=1000,
        end_date=None
    )
    membership.save()

    processing_date = datetime.utcnow().replace(tzinfo=timezone.utc)
    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status
    assert updated_ixp.last_updated == ixp.last_updated


def test_active_ixp_with_member_marked_ended_is_marked_inactive():
    ixp = create_ixp_fixture(1)
    asn = create_asn_fixture(12345)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=ixp.last_updated,
        last_active=ixp.last_active
    )
    member.save()
    end_date = processing_date.replace(day=1) - timedelta(days=1)
    membership = IXPMembershipRecord(
        member=member,
        start_date=ixp.created,
        is_rs_peer=True,
        speed=1000,
        end_date=end_date
    )
    membership.save()

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status is False
    assert updated_ixp.last_updated == processing_date


def test_inactive_ixp_with_no_active_members_remains_inactive():
    ixp = create_ixp_fixture(1)
    ixp.active_status = False
    ixp.save()
    asn = create_asn_fixture(12345)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=ixp.last_updated,
        last_active=ixp.last_active
    )
    member.save()
    end_date = processing_date.replace(day=1) - timedelta(days=1)
    membership = IXPMembershipRecord(
        member=member,
        start_date=ixp.created,
        is_rs_peer=True,
        speed=1000,
        end_date=end_date
    )
    membership.save()

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status is False
    assert updated_ixp.last_updated == ixp.last_updated


def test_inactive_ixp_with_active_member_marked_active():
    ixp = create_ixp_fixture(1)
    ixp.active_status = False
    ixp.save()
    asn = create_asn_fixture(12345)
    member = IXPMember(
        ixp=ixp,
        asn=asn,
        last_updated=ixp.last_updated,
        last_active=ixp.last_active
    )
    member.save()
    membership = IXPMembershipRecord(
        member=member,
        start_date=ixp.created,
        is_rs_peer=True,
        speed=1000,
        end_date=None
    )
    membership.save()

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status
    assert updated_ixp.last_updated == processing_date
