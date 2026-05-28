from datetime import timezone
from uuid import UUID
import pytest
from faker import Faker

from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore, Event, Aggregate
from ixp_tracker.ixp_tracker import IXPTracker, IXP_TRACKER_EVENT_MAP, ASNList, IXPMember, IXPIdMapProjection
from tests.fixtures import create_ixp, create_asn, create_member
from ixp_tracker.models import StoredEvent

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
        return [event for event in self.events if event.aggregate_id == aggregate_id]


def test_adds_member_that_does_not_already_exist(faker: Faker):
    app, es = build_app()

    ixp = create_ixp(faker, es)
    asn = create_asn(faker, es)
    assert len(ixp.get_members()) == 0

    member = app.register_member(
        ixp,
        asn.number,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.boolean(),
        faker.random_number(digits=5),
    )

    assert member.asn_id == asn.id

    members = ixp.get_members()
    assert len(members) == 1
    assert member.id in members


def test_updates_existing_member(faker: Faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    member = create_member(faker, es)

    new_port_speed = faker.random_number(digits=5)
    processing_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    app.update_member(
        member,
        member.created_date,
        member.updated_date,
        processing_date,
        member.is_rs_peer,
        new_port_speed
    )

    [_ixp_created, _asn_created, _member_created, update_event, _last_active] = mes.events
    assert update_event.event_type == "IXPMemberUpdated"
    assert update_event.data["port_speed"] == new_port_speed


def test_does_not_update_fields_if_not_changed(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    member = create_member(faker, es)

    processing_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    app.update_member(
        member,
        member.created_date,
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        processing_date,
        member.is_rs_peer,
        member.port_speed
    )

    [_ixp_created, _asn_created, _member_created, update_event, _last_active] = mes.events

    # only updated_date has changed, other fields marked unchanged
    assert update_event.data.get("created_date", None) is None
    assert update_event.data.get("port_speed", None) is None


def test_always_updates_last_active(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    member = create_member(faker, es)

    processing_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)
    member = app.update_member(
        member,
        member.created_date,
        member.updated_date,
        processing_date,
        member.is_rs_peer,
        member.port_speed
    )

    [_ixp_created, _asn_created, _member_created, last_active_update] = mes.events

    assert last_active_update.event_type == "MemberActiveInPeeringDb"
    assert member.last_active.date() == processing_date.date()


def test_registers_change_in_rs_peering_status(faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)
    member = create_member(faker, es)
    member.is_rs_peer = False
    processing_date = faker.date_time_between(start_date="-1d", tzinfo=timezone.utc)

    member = app.update_member(
        member,
        member.created_date,
        member.updated_date,
        processing_date,
        not member.is_rs_peer,
        member.port_speed
    )

    [_ixp_created, _asn_created, _member_created, rs_peer_update_event, _last_active] = mes.events

    assert rs_peer_update_event.event_type == "RsPeeringStatusChange"
    assert member.is_rs_peer



def build_app(es_db: EventStorePersistence = None) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    app = IXPTracker(es)
    return app, es
