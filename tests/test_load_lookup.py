import pytest

from ixp_tracker.management.commands.ixp_tracker_import import DefaultAdditionalDataSources, load_lookup


def test_with_no_name_returns_none():
    data_lookup = load_lookup(None)

    assert data_lookup is None


def test_with_empty_name_returns_none():
    data_lookup = load_lookup("")

    assert data_lookup is None


def test_with_invalid_module():
    with pytest.raises(Exception):
        load_lookup("foobar.factory")


def test_with_invalid_factory():
    with pytest.raises(Exception):
        load_lookup("django_test_app.factory.foobar")


def test_loads_lookup():
    data_lookup = load_lookup("django_test_app.factory.return_data_lookup")

    assert isinstance(data_lookup, DefaultAdditionalDataSources)
