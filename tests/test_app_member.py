from datetime import timezone

import pytest
from faker import Faker

from ixp_tracker.event_store import EventStorePersistence, EventStore, DjangoEventStore
from ixp_tracker.ixp_tracker import IXPTracker, IXP_TRACKER_EVENT_MAP, ASNList
from tests.fixtures import create_ixp, create_asn

pytestmark = pytest.mark.django_db


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


def build_app(es_db: EventStorePersistence = None) -> tuple[IXPTracker, EventStore]:
    es = EventStore(IXP_TRACKER_EVENT_MAP, es_db or DjangoEventStore())
    es.add_listener(ASNList())
    app = IXPTracker(es)
    return app, es
