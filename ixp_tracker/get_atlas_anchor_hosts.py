def get_atlas_anchor_hosts(
    ixp_data: list[dict], asn_data: list[dict], anchor_host_asns: list[int]
) -> list[int]:
    ixps_with_atlas_anchor = set()
    for asn in anchor_host_asns:
        net_record = next((net for net in asn_data if net["asn"] == asn), None)
        if net_record is None:
            continue
        ixp_records = [
            ixp["id"] for ixp in ixp_data if net_record["org_id"] == ixp["org_id"]
        ]
        ixps_with_atlas_anchor |= set(ixp_records)
    return list(ixps_with_atlas_anchor)
