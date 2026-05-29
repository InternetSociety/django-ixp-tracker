from datetime import timezone
from uuid import UUID
import pytest
from faker import Faker

from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore, Event, StoredEvent, Aggregate
from ixp_tracker.ixp_tracker import IXPTracker, IXP_TRACKER_EVENT_MAP, ASNList, IXPIdMapProjection
from tests.fixtures import create_ixp, create_asn

pytestmark = pytest.mark.django_db


class MemoryEventStore(EventStorePersistence):
    events: list = []
    sequence = 0

    def __init__(self):
        self.events = []

    def get_event_sequence(self, event: Event) -> int:
        self.sequence = self.sequence + 1
        return self.sequence

    def save_event(self, event: StoredEvent):
        self.events.append(event)

    def get_aggregate_events(
        self, aggregate_id: UUID, aggregate_type: type[Aggregate]
    ) -> list[StoredEvent]:
        return self.events


def test_adds_member_that_does_not_already_exist(faker: Faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn = create_asn(faker, es)
    print(mes.events)
    ixp = create_ixp(faker, es)

    assert len(ixp.get_members()) == 0

    app.import_members(
        ixp.peeringdb_id,
        [{
            "asn": asn.number,
            "created_date": faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
            "updated_date": faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
            "is_rs_peer": faker.boolean(),
            "port_speed": faker.random_number(digits=5),
        },]
    )

    members = ixp.get_members()
    assert len(members) == 1
    assert asn.number == members[0].asn


def build_app(es_db: EventStorePersistence = None) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    app = IXPTracker(es)
    return app, es
