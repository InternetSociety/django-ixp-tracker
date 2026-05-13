import pytest

from ixp_tracker.ixp_tracker import ISOCIdProjection
from ixp_tracker.models import ISOCId
from tests.fixtures import StoredEventFactory

pytestmark = pytest.mark.django_db


def test_creates_new_isoc_id(faker):
    projection = ISOCIdProjection()
    event = StoredEventFactory()

    current = ISOCId.objects.all()
    assert current.count() == 0

    projection.handle(event)

    saved = ISOCId.objects.get(aggregate_id=event.aggregate_id)
    assert saved.id > 0
