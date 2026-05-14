import pytest

from tests.fixtures import StoredEventFactory, TestProjection

# We need to use the db/Django-stored events here for now as the `EventStore` passes those to all projections
# even though the projection we're testing doesn't need a db. Perhaps a future refactoring?
pytestmark = pytest.mark.django_db


def test_handles_specified_aggregate():
    event = StoredEventFactory(
        event_type="CreatedTestAggregate", aggregate_type="TestAggregate"
    )
    projection = TestProjection()

    projection.handle(event)

    assert projection.handled


def test_does_not_handle_different_aggregate():
    event = StoredEventFactory(
        event_type="CreatedTestAggregate", aggregate_type="SecondAggregate"
    )
    projection = TestProjection()

    projection.handle(event)

    assert projection.handled is False


def test_does_not_handle_different_event():
    event = StoredEventFactory(
        event_type="AnotherEvent", aggregate_type="TestAggregate"
    )
    projection = TestProjection()

    projection.handle(event)

    assert projection.handled is False
