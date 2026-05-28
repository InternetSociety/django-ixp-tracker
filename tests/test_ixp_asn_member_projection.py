import pytest

from ixp_tracker.ixp_tracker import MemberMapProjection
from ixp_tracker.models import IXPASNMemberMap
from tests.fixtures import StoredEventFactory
from uuid import uuid4
pytestmark = pytest.mark.django_db


def test_adds_new_member(faker):
    projection = MemberMapProjection()
    ixp_id = uuid4()
    asn_id = uuid4()
    event = StoredEventFactory(
        event_type="IXPMemberCreated", aggregate_type="IXPMember", data={"ixp_id": str(ixp_id), "asn_id": str(asn_id)}
    )

    current = IXPASNMemberMap.objects.all()
    assert current.count() == 0

    projection.handle(event)

    saved = IXPASNMemberMap.objects.get(aggregate_id=event.aggregate_id)
    assert saved.ixp_id == ixp_id
    assert saved.asn_id == asn_id


def test_handles_duplicate_events(faker):
    projection = MemberMapProjection()
    ixp_id = uuid4()
    asn_id = uuid4()
    event = StoredEventFactory(
        event_type="IXPMemberCreated", aggregate_type="IXPMember", data={"ixp_id": str(ixp_id), "asn_id": str(asn_id)}
    )

    # This shouldn't happen but if it does we just handle it silently
    # If this becomes a problem we could add event sequence tracking to projections
    projection.handle(event)
    projection.handle(event)

    saved = IXPASNMemberMap.objects.all()
    assert saved.count() == 1
