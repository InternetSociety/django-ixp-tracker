from ixp_tracker.event_store import EventStore
from ixp_tracker.ixp_tracker import as_zz_country_check
from ixp_tracker.ixp_tracker_aggregates import IXP_TRACKER_EVENT_MAP, NROStatus
from tests.fixtures import MemoryEventStore, create_asn


def test_as_not_registered_to_zz_returns_false(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es)

    assert as_zz_country_check(asn) is False


def test_as_registered_to_zz_and_not_assigned_returns_true(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es, country_code="ZZ", nro_status=NROStatus.AVAILABLE)

    assert as_zz_country_check(asn)


def test_as_registered_to_zz_but_assigned_returns_false(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es, country_code="ZZ", nro_status=NROStatus.ASSIGNED)

    assert as_zz_country_check(asn) is False


def test_as112_returns_false(faker):
    es = EventStore(IXP_TRACKER_EVENT_MAP, MemoryEventStore())
    asn = create_asn(faker, es, country_code="ZZ", asn=112)

    assert as_zz_country_check(asn) is False
