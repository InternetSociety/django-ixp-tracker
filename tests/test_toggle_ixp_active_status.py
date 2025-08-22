import pytest
from datetime import datetime, timedelta, timezone

from ixp_tracker.importers import toggle_ixp_active_status
from ixp_tracker.models import IXP
from tests.fixtures import IXPFactory, create_member_fixture

pytestmark = pytest.mark.django_db
processing_date = datetime.now(timezone.utc)


def test_active_ixp_with_3_members_remains_active():
    ixp = IXPFactory(active_status=True)
    create_member_fixture(ixp, quantity=3)

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=ixp.peeringdb_id)

    assert updated_ixp.active_status
    assert updated_ixp.last_updated == ixp.last_updated


def test_active_ixp_gone_from_three_to_two_active_members_is_marked_inactive():
    end_date = processing_date.replace(day=1) - timedelta(days=1)
    ixp = IXPFactory(active_status=True)
    create_member_fixture(ixp, quantity=2)
    create_member_fixture(ixp, membership_properties={"end_date": end_date})

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=ixp.peeringdb_id)

    assert updated_ixp.active_status is False
    assert updated_ixp.last_updated == processing_date


def test_inactive_ixp_with_two_active_members_remains_inactive():
    end_date = processing_date.replace(day=1) - timedelta(days=1)
    ixp = IXPFactory(active_status=False)
    create_member_fixture(ixp, quantity=2)
    create_member_fixture(ixp, membership_properties={"end_date": end_date})

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=ixp.peeringdb_id)

    assert updated_ixp.active_status is False
    assert updated_ixp.last_updated == ixp.last_updated


def test_inactive_ixp_with_three_active_members_marked_active():
    ixp = IXPFactory(active_status=False)
    create_member_fixture(ixp, quantity=3)

    toggle_ixp_active_status(processing_date)

    updated_ixp = IXP.objects.get(peeringdb_id=ixp.peeringdb_id)

    assert updated_ixp.active_status
    assert updated_ixp.last_updated == processing_date
