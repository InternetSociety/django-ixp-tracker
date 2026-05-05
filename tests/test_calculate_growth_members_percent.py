from random import randint

from ixp_tracker.stats import calculate_growth_members_percent


def test_member_growth_is_zero_returns_zero():
    member_growth = 0
    num_members_last_month = randint(1, 100)
    gmp = calculate_growth_members_percent(member_growth, num_members_last_month)

    assert gmp == 0.0


def test_member_growth_is_calculated_correctly():
    member_growth = randint(1, 100)
    num_members_last_month = randint(1, 100)
    gmp = calculate_growth_members_percent(member_growth, num_members_last_month)

    assert gmp == member_growth / num_members_last_month


def test_growth_from_zero_returns_one():
    member_growth = randint(1, 100)
    num_members_last_month = 0
    gmp = calculate_growth_members_percent(member_growth, num_members_last_month)

    assert gmp == 1.0


def test_no_growth_and_no_members_returns_zero():
    member_growth = 0
    num_members_last_month = 0
    gmp = calculate_growth_members_percent(member_growth, num_members_last_month)

    assert gmp == 0.0
