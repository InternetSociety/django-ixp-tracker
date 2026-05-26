from ixp_tracker.importers import dedupe_member_data
from tests.fixtures import PeeringNetIXLANFactory


def test_deduplicates_member_data_before_processing():
    member_import = PeeringNetIXLANFactory()
    duplicate_one = PeeringNetIXLANFactory(
        ix_id=member_import["ix_id"], asn=member_import["asn"]
    )
    duplicate_two = PeeringNetIXLANFactory(
        ix_id=member_import["ix_id"], asn=member_import["asn"]
    )

    deduplicated_data = dedupe_member_data(
        [member_import, duplicate_one, duplicate_two]
    )

    assert len(deduplicated_data) == 1


def test_set_rs_peer_to_true_if_any_member_is_set_to_true():
    member_import = PeeringNetIXLANFactory(is_rs_peer=False)
    duplicate_one = PeeringNetIXLANFactory(
        ix_id=member_import["ix_id"], asn=member_import["asn"], is_rs_peer=True
    )
    duplicate_two = PeeringNetIXLANFactory(
        ix_id=member_import["ix_id"], asn=member_import["asn"], is_rs_peer=False
    )

    deduplicated_data = dedupe_member_data(
        [member_import, duplicate_one, duplicate_two]
    )

    deduplicated_member = deduplicated_data[0]
    assert deduplicated_member["is_rs_peer"]


def test_speed_for_deduped_members_is_sum_of_all_speeds():
    member_import = PeeringNetIXLANFactory(speed=500)
    duplicate_one = PeeringNetIXLANFactory(
        ix_id=member_import["ix_id"], asn=member_import["asn"], speed=1000
    )
    duplicate_two = PeeringNetIXLANFactory(
        ix_id=member_import["ix_id"], asn=member_import["asn"], speed=3000
    )

    deduplicated_data = dedupe_member_data(
        [member_import, duplicate_one, duplicate_two]
    )

    deduplicated_member = deduplicated_data[0]
    assert deduplicated_member["speed"] == 4500
