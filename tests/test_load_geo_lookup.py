import pytest

from ixp_tracker.management.commands.ixp_tracker_import import DefaultASNGeoLookup, load_geo_lookup


def test_with_no_name_returns_none():
    geo_lookup = load_geo_lookup(None)

    assert geo_lookup is None


def test_with_empty_name_returns_none():
    geo_lookup = load_geo_lookup("")

    assert geo_lookup is None


def test_with_invalid_module():
    with pytest.raises(Exception):
        load_geo_lookup("foobar.factory")


def test_with_invalid_factory():
    with pytest.raises(Exception):
        load_geo_lookup("django_test_app.factory.foobar")


def test_loads_lookup():
    geo_lookup = load_geo_lookup("django_test_app.factory.return_geo_lookup")

    assert isinstance(geo_lookup, DefaultASNGeoLookup)
