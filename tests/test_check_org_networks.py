from datetime import datetime, timezone

from ixp_tracker.check_org_networks import check_org_networks
from ixp_tracker.data_lookup import ASNGeoLookup
from tests.fixtures import MockLookup, PeeringIXFactory, PeeringASNFactory

test_date = datetime.now(tz=timezone.utc)


def test_with_no_ixs_returns_nothing():
    ixs = []
    networks = []

    ix_checks = check_org_networks(ixs, networks, MockLookup(), test_date)

    assert ix_checks == {}


def test_ix_with_no_org_returns_none():
    ixp = PeeringIXFactory()
    ixp["org_id"] = None
    ixs = [ixp]
    networks = []

    ix_checks = check_org_networks(ixs, networks, MockLookup(), test_date)

    assert ix_checks == {ixp["id"]: None}


def test_ix_org_with_no_networks_returns_none():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    networks = []

    ix_checks = check_org_networks(ixs, networks, MockLookup(), test_date)

    assert ix_checks == {ixp["id"]: None}


def test_ix_org_with_one_active_network_returns_true():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    net = PeeringASNFactory(org_id=ixp["org_id"])
    networks = [net]

    ix_checks = check_org_networks(ixs, networks, MockLookup(), test_date)

    assert ix_checks == {ixp["id"]: True}


def test_ix_org_with_one_network_available_only_recently_returns_true():
    class TimeBasedASNGeoLookup(ASNGeoLookup):
        def get_iso2_country(self, asn: int, as_at: datetime) -> str:
            if as_at == test_date:
                return "ZZ"
            else:
                return "US"

        def get_status(self, asn: int, as_at: datetime) -> str:
            return "assigned"

        def get_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
            return []

        def get_routed_asns_for_country(
            self, country: str, as_at: datetime
        ) -> list[int]:
            return []

    ixp = PeeringIXFactory()
    ixs = [ixp]
    net = PeeringASNFactory(org_id=ixp["org_id"])
    networks = [net]

    ix_checks = check_org_networks(ixs, networks, TimeBasedASNGeoLookup(), test_date)

    assert ix_checks == {ixp["id"]: True}


def test_ix_org_with_one_network_available_but_not_in_zz_returns_true():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    net = PeeringASNFactory(org_id=ixp["org_id"])
    networks = [net]

    ix_checks = check_org_networks(
        ixs,
        networks,
        MockLookup(default_status="available", default_country="FR"),
        test_date,
    )

    assert ix_checks == {ixp["id"]: True}


def test_ix_org_with_one_network_in_zz_but_assigned_returns_true():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    net = PeeringASNFactory(org_id=ixp["org_id"])
    networks = [net]

    ix_checks = check_org_networks(
        ixs,
        networks,
        MockLookup(default_country="ZZ", default_status="assigned"),
        test_date,
    )

    assert ix_checks == {ixp["id"]: True}


def test_always_returns_true_for_112():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    net = PeeringASNFactory(org_id=ixp["org_id"], asn=112)
    networks = [net]

    ix_checks = check_org_networks(
        ixs,
        networks,
        MockLookup(default_country="ZZ", default_status="reserved"),
        test_date,
    )

    assert ix_checks == {ixp["id"]: True}


def test_ix_org_with_one_network_in_zz_and_not_assigned_returns_false():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    net = PeeringASNFactory(org_id=ixp["org_id"])
    networks = [net]

    ix_checks = check_org_networks(
        ixs,
        networks,
        MockLookup(default_country="ZZ", default_status="reserved"),
        test_date,
    )

    assert ix_checks == {ixp["id"]: False}


def test_returns_true_with_one_network_active_and_one_not():
    ixp = PeeringIXFactory()
    ixs = [ixp]
    active_net = PeeringASNFactory(org_id=ixp["org_id"])
    inactive_net = PeeringASNFactory(org_id=ixp["org_id"])
    networks = [active_net, inactive_net]

    class ASNBasedASNGeoLookup(ASNGeoLookup):
        def get_iso2_country(self, asn: int, as_at: datetime) -> str:
            if asn == inactive_net["asn"]:
                return "ZZ"
            else:
                return "US"

        def get_status(self, asn: int, as_at: datetime) -> str:
            return "available"

        def get_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
            return []

        def get_routed_asns_for_country(
            self, country: str, as_at: datetime
        ) -> list[int]:
            return []

    ix_checks = check_org_networks(ixs, networks, ASNBasedASNGeoLookup(), test_date)

    assert ix_checks == {ixp["id"]: True}
