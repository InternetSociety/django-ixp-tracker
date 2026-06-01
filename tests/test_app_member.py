from datetime import datetime, timezone
import pytest
from faker import Faker

from ixp_tracker.event_store import (
    EventStorePersistence,
    EventStore,
    DjangoEventStore,
)
from ixp_tracker.ixp_tracker import (
    IXPTracker,
    IXP_TRACKER_EVENT_MAP,
    ASNList,
    IXPIdMapProjection,
)
from tests.fixtures import create_ixp, create_asn, MemoryEventStore

pytestmark = pytest.mark.django_db

date_now = datetime.now(timezone.utc)


def test_imports_member(faker: Faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn = create_asn(faker, es)
    ixp = create_ixp(faker, es)

    assert len(ixp.get_members()) == 0

    imported = app.import_members(
        ixp,
        [
            {
                "asn": asn.number,
                "created_date": faker.date_time_between(
                    start_date="-1d", tzinfo=timezone.utc
                ),
                "updated_date": faker.date_time_between(
                    start_date="-1d", tzinfo=timezone.utc
                ),
                "last_active": date_now,
                "is_rs_peer": faker.boolean(),
                "port_speed": faker.random_number(digits=5),
            },
        ],
    )
    members = imported.get_members()
    assert len(members) == 1
    assert asn.number in members.keys()


def test_imports_multiple_members(faker: Faker):
    mes = MemoryEventStore()
    app, es = build_app(mes)

    asn1 = create_asn(faker, es)
    asn2 = create_asn(faker, es)
    ixp = create_ixp(faker, es)

    assert len(ixp.get_members()) == 0

    imported = app.import_members(
        ixp,
        [
            {
                "asn": asn1.number,
                "created_date": faker.date_time_between(
                    start_date="-1d", tzinfo=timezone.utc
                ),
                "updated_date": faker.date_time_between(
                    start_date="-1d", tzinfo=timezone.utc
                ),
                "last_active": date_now,
                "is_rs_peer": faker.boolean(),
                "port_speed": faker.random_number(digits=5),
            },
            {
                "asn": asn2.number,
                "created_date": faker.date_time_between(
                    start_date="-1d", tzinfo=timezone.utc
                ),
                "updated_date": faker.date_time_between(
                    start_date="-1d", tzinfo=timezone.utc
                ),
                "last_active": date_now,
                "is_rs_peer": faker.boolean(),
                "port_speed": faker.random_number(digits=5),
            },
        ],
    )

    members = imported.get_members().keys()
    assert len(members) == 2
    assert asn1.number in members
    assert asn2.number in members


def build_app(
    es_db: EventStorePersistence | None = None,
) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(IXPIdMapProjection())
    es.add_listener(ASNList())
    app = IXPTracker(es)
    return app, es
