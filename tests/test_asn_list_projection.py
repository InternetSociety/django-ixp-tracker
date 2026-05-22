import pytest

from ixp_tracker.ixp_tracker import ASNList
from ixp_tracker.models import ASNMap
from tests.fixtures import StoredEventFactory

pytestmark = pytest.mark.django_db


def test_adds_new_asn(faker):
    projection = ASNList()
    asn = faker.random_number(digits=5)
    event = StoredEventFactory(
        event_type="ASNCreated", aggregate_type="ASN", data={"as_number": asn}
    )

    current = ASNMap.objects.all()
    assert current.count() == 0

    projection.handle(event)

    saved = ASNMap.objects.get(aggregate_id=event.aggregate_id)
    assert saved.asn == asn


def test_handles_duplicate_events(faker):
    projection = ASNList()
    asn = faker.random_number(digits=5)
    event = StoredEventFactory(
        event_type="ASNCreated", aggregate_type="ASN", data={"as_number": asn}
    )

    # This shouldn't happen but if it does we just handle it silently
    # If this becomes a problem we could add event sequence tracking to projections
    projection.handle(event)
    projection.handle(event)

    saved = ASNMap.objects.all()
    assert saved.count() == 1
