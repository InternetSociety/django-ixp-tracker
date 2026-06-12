from datetime import timedelta, timezone, datetime

from ixp_tracker.ixp_tracker import check_if_members_have_left
from ixp_tracker.ixp_tracker_aggregates import IXPMemberDetails
from tests.fixtures import TestLookup

date_now = datetime.now(timezone.utc)


def test_marks_member_as_left_that_is_no_longer_active(faker):
    first_day_of_month = date_now.replace(day=1)
    last_day_of_last_month = first_day_of_month - timedelta(days=1)
    date_more_than_month_ago = last_day_of_last_month - timedelta(days=17)

    as_number = faker.random_number(digits=5)
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(
            faker, date_more_than_month_ago, date_more_than_month_ago
        )
    }

    members_left = check_if_members_have_left(members, date_now, TestLookup())

    expected_end_date = last_day_of_last_month
    assert len(members_left) == 1
    assert members_left[0][0] == as_number
    assert members_left[0][1] == expected_end_date


def test_marks_as112_as_left_if_no_longer_active(faker):
    first_day_of_month = date_now.replace(day=1)
    last_day_of_last_month = first_day_of_month - timedelta(days=1)
    date_more_than_month_ago = last_day_of_last_month - timedelta(days=17)

    as_number = 112
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(
            faker, date_more_than_month_ago, date_more_than_month_ago
        )
    }

    members_left = check_if_members_have_left(members, date_now, TestLookup())

    expected_end_date = last_day_of_last_month
    assert len(members_left) == 1
    assert members_left[0][0] == as_number
    assert members_left[0][1] == expected_end_date


def test_does_not_mark_member_as_left_if_asn_is_registered_in_country_zz_and_is_assigned(
    faker,
):
    as_number = faker.random_number(digits=5)
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = check_if_members_have_left(
        members, date_now, TestLookup(default_country="ZZ", default_status="assigned")
    )

    assert len(members_left) == 0


def test_does_not_mark_member_as_left_if_asn_is_registered_in_valid_country_and_is_not_assigned(
    faker,
):
    as_number = faker.random_number(digits=5)
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = check_if_members_have_left(
        members,
        date_now,
        TestLookup(default_country=faker.country_code(), default_status="unassigned"),
    )

    assert len(members_left) == 0


def test_marks_member_as_left_if_asn_is_registered_in_country_zz_and_is_not_assigned(
    faker,
):
    as_number = faker.random_number(digits=5)
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = check_if_members_have_left(
        members, date_now, TestLookup(default_country="ZZ", default_status="unassigned")
    )

    assert len(members_left) == 1


def test_does_not_mark_as112_as_left_if_registered_in_country_zz_and_is_not_assigned(
    faker,
):
    as_number = 112
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = check_if_members_have_left(
        members, date_now, TestLookup(default_country="ZZ", default_status="unassigned")
    )

    assert len(members_left) == 0


def test_does_not_mark_as_left_before_joining_date(faker):
    first_day_of_month = date_now.replace(day=1)

    as_number = faker.random_number(digits=5)
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(
            faker, start_date=first_day_of_month, last_active=date_now
        )
    }

    members_left = check_if_members_have_left(members, date_now, TestLookup())

    assert len(members_left) == 0


def create_member_details(
    faker, start_date: datetime | None = None, last_active: datetime | None = None
) -> IXPMemberDetails:
    return IXPMemberDetails(
        start_date or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        last_active or faker.date_time_between(start_date="-1d", tzinfo=timezone.utc),
        faker.boolean(),
        faker.random_number(digits=5),
        None,
    )
