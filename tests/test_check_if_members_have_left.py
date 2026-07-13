from datetime import timedelta, timezone, datetime

import pytest
from ixp_tracker.ixp_tracker_aggregates import IXPMemberDetails, NROStatus
from tests.fixtures import build_app, create_asn

pytestmark = pytest.mark.django_db
date_now = datetime.now(timezone.utc)


def test_marks_member_as_left_that_is_no_longer_active(faker):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)
    last_day_of_last_month = first_day_of_month - timedelta(days=1)
    date_more_than_month_ago = last_day_of_last_month - timedelta(days=17)

    asn = create_asn(faker, es)
    as_number = asn.number
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(
            faker, date_more_than_month_ago, date_more_than_month_ago
        )
    }

    members_left = app.check_if_members_have_left(members, date_now)

    expected_end_date = last_day_of_last_month
    assert len(members_left) == 1
    assert members_left[0][0] == as_number
    assert members_left[0][1] == expected_end_date


def test_marks_as112_as_left_if_no_longer_active(faker):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)
    last_day_of_last_month = first_day_of_month - timedelta(days=1)
    date_more_than_month_ago = last_day_of_last_month - timedelta(days=17)

    as_number = 112
    create_asn(faker, es, asn=as_number)
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(
            faker, date_more_than_month_ago, date_more_than_month_ago
        )
    }

    members_left = app.check_if_members_have_left(members, date_now)

    expected_end_date = last_day_of_last_month
    assert len(members_left) == 1
    assert members_left[0][0] == as_number
    assert members_left[0][1] == expected_end_date


def test_does_not_mark_member_as_left_if_asn_is_registered_in_country_zz_and_is_assigned(
    faker,
):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)

    asn = create_asn(faker, es)
    as_number = asn.number
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = app.check_if_members_have_left(
        members, date_now
    )  # , MockLookup(default_country="ZZ", default_status="assigned")

    assert len(members_left) == 0


def test_does_not_mark_member_as_left_if_asn_is_registered_in_valid_country_and_is_not_assigned(
    faker,
):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)

    asn = create_asn(faker, es)
    as_number = asn.number
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = app.check_if_members_have_left(members, date_now)
    # MockLookup(default_country=faker.country_code(), default_status="unassigned"),

    assert len(members_left) == 0


def test_marks_member_as_left_if_asn_is_registered_in_country_zz_and_is_not_assigned(
    faker,
):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)

    asn = create_asn(faker, es, country_code="ZZ", nro_status=NROStatus.AVAILABLE)
    as_number = asn.number
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = app.check_if_members_have_left(members, date_now)

    assert len(members_left) == 1


def test_does_not_mark_as112_as_left_if_registered_in_country_zz_and_is_not_assigned(
    faker,
):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)

    as_number = 112
    create_asn(
        faker, es, asn=as_number, country_code="ZZ", nro_status=NROStatus.RESERVED
    )
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(faker, last_active=date_now)
    }

    members_left = app.check_if_members_have_left(members, date_now)

    assert len(members_left) == 0


def test_does_not_mark_as_left_before_joining_date(faker):
    app, es = build_app()
    first_day_of_month = date_now.replace(day=1)
    app.time_travel(first_day_of_month)

    asn = create_asn(faker, es)
    as_number = asn.number
    members: dict[int, IXPMemberDetails] = {
        as_number: create_member_details(
            faker, start_date=first_day_of_month, last_active=date_now
        )
    }

    members_left = app.check_if_members_have_left(members, date_now)

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
