from ixp_tracker.stats import calculate_local_asns_members_rate


def test_calculate_local_asns_members_rate_returns_zero_if_no_asns_in_country():
    rate = calculate_local_asns_members_rate([12345], [])

    assert rate == 0


def test_calculate_local_asns_members_rate():
    rate = calculate_local_asns_members_rate([12345], [12345, 446, 789, 5050, 54321])

    assert rate == 0.2


def test_calculate_local_asns_members_rate_ignores_members_not_in_country_list():
    rate = calculate_local_asns_members_rate([12345, 789], [12345, 446, 5050, 54321])

    assert rate == 0.25
