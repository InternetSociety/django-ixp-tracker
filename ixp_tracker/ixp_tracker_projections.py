from ixp_tracker.event_store import Projection, Aggregate
from ixp_tracker.ixp_tracker_aggregates import (
    IXPCreated,
    ASNCreated,
    ASN,
    IXP,
    IXPMemberJoined,
    RsPeeringStatusChange,
    IXPMemberActiveInPeeringDb,
    IXPMemberLeft,
    PortSpeedUpdated,
)
from ixp_tracker.models import (
    StoredEvent,
    ASNMap,
    IXPIdMap,
    IXP as LegacyIXP,
    IXPMembers,
)


class ASNList(Projection):
    aggregate_types = [ASN.__name__]
    events = [ASNCreated.__name__]

    def do_handle(self, event: StoredEvent, asn: Aggregate):
        existing = ASNMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        asn = event.data.get("as_number", None)
        asn_map = ASNMap(
            aggregate_id=event.aggregate_id,
            asn=asn,
        )
        asn_map.save()


class IXPIdMapProjection(Projection):
    aggregate_types = [IXP.__name__]
    events = [IXPCreated.__name__]

    def do_handle(self, event: StoredEvent, aggregate: Aggregate):
        existing = IXPIdMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        peeringdb_id = event.data.get("peeringdb_id", None)
        preserve_legacy_id = LegacyIXP.objects.filter(peeringdb_id=peeringdb_id).first()
        if preserve_legacy_id:
            # If a legacy object exists, use that's primary key as our primary key to preserve the "isoc_id"
            isoc_id = IXPIdMap(
                id=preserve_legacy_id.pk,
                aggregate_id=event.aggregate_id,
                peeringdb_id=peeringdb_id,
            )
        else:
            isoc_id = IXPIdMap(
                aggregate_id=event.aggregate_id,
                peeringdb_id=peeringdb_id,
            )
        isoc_id.save()

    def find_by_peeringdb_id(self, peeringdb_id: int) -> IXPIdMap | None:
        try:
            return IXPIdMap.objects.get(peeringdb_id=peeringdb_id)
        except IXPIdMap.DoesNotExist:
            return None


class IXPMemberProjection(Projection):
    aggregate_types = [IXP.__name__]
    events = [
        IXPMemberActiveInPeeringDb.__name__,
        IXPMemberJoined.__name__,
        IXPMemberLeft.__name__,
        PortSpeedUpdated.__name__,
        RsPeeringStatusChange.__name__,
    ]

    def do_handle(self, event: StoredEvent, ixp: Aggregate):
        if not isinstance(ixp, IXP):
            return
        asn = int(event.data["asn"])
        member = ixp.get_members(True)[asn]
        IXPMembers.objects.update_or_create(
            ixp_id=event.aggregate_id,
            asn=asn,
            defaults={
                "date_joined": member.date_joined,
                "date_left": member.date_left,
                "is_rs_peer": member.is_rs_peer,
                "port_speed": member.port_speed,
            },
        )
