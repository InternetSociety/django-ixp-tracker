import pytest
from datetime import datetime, timedelta, timezone

from ixp_tracker.importers import toggle_ixp_active_status
from ixp_tracker.models import IXP
from tests.fixtures import create_ixp_fixture, create_member_fixture

pytestmark = pytest.mark.django_db
processing_date = datetime.now(timezone.utc)


def test_active_ixp_with_3_members_remains_active():
    ixp = create_ixp_fixture(1)
    create_member_fixture(ixp, 12345)
    create_member_fixture(ixp, 23456)
    create_member_fixture(ixp, 34567)

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status
    assert updated_ixp.last_updated == ixp.last_updated


def test_active_ixp_gone_from_three_to_two_active_members_is_marked_inactive():
    ixp = create_ixp_fixture(1)
    end_date = processing_date.replace(day=1) - timedelta(days=1)
    create_member_fixture(ixp, 12345)
    create_member_fixture(ixp, 23456)
    create_member_fixture(ixp, 34567, date_left=end_date)

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status is False
    assert updated_ixp.last_updated == processing_date


def test_inactive_ixp_with_two_active_members_remains_inactive():
    ixp = create_ixp_fixture(1)
    ixp.active_status = False
    ixp.save()
    end_date = processing_date.replace(day=1) - timedelta(days=1)
    create_member_fixture(ixp, 12345)
    create_member_fixture(ixp, 23456)
    create_member_fixture(ixp, 34567, date_left=end_date)

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status is False
    assert updated_ixp.last_updated == ixp.last_updated


def test_inactive_ixp_with_three_active_members_marked_active():
    ixp = create_ixp_fixture(1)
    ixp.active_status = False
    ixp.save()
    create_member_fixture(ixp, 12345)
    create_member_fixture(ixp, 23456)
    create_member_fixture(ixp, 34567)

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=1)

    assert updated_ixp.active_status
    assert updated_ixp.last_updated == processing_date
