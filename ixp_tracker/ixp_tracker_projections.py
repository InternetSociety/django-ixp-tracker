from datetime import date

from ixp_tracker.event_store import Projection, Aggregate
from ixp_tracker.ixp_tracker_aggregates import (
    IXPCreated,
    ASNCreated,
    ASN,
    IXP,
    IXP_TRACKER_EVENT_MAP,
    IXPMemberActiveInPeeringDb,
    IXPActiveInPeeringDb,
)
from ixp_tracker.models import (
    StoredEvent,
    ASNMap,
    IXPIdMap,
    IXP as LegacyIXP,
    UpdatedIXPs,
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


class IXPsLastUpdatedProjection(Projection):
    aggregate_types = [IXP.__name__]

    def __init__(self):
        self.events = []
        # We need to make sure we handle any IXP events that make changes so this feels like the most reliable way to do that
        for event_type in IXP_TRACKER_EVENT_MAP.keys():
            if event_type.startswith("ASN"):
                continue
            # We don't need the "last_active" events though as they don't materially change the aggregates
            if event_type in [
                IXPActiveInPeeringDb.__name__,
                IXPMemberActiveInPeeringDb.__name__,
            ]:
                continue
            self.events.append(event_type)
        super().__init__()
        self.id_map = IXPIdMapProjection()

    def do_handle(self, event: StoredEvent, ixp: Aggregate):
        if not isinstance(ixp, IXP):
            return
        ids = self.id_map.find_by_peeringdb_id(ixp.peeringdb_id)
        if ids is None:
            return
        UpdatedIXPs.objects.update_or_create(
            aggregate_id=ixp.id,
            isoc_id=ids.id,
            defaults={
                "last_updated": event.event_date.date(),
                "data": ixp.snapshot(),
            },
        )

    def ixps_updated_since(
        self, since: date | None, count: int, first_id: int
    ) -> list[UpdatedIXPs]:
        updated = UpdatedIXPs.objects.filter(isoc_id__gte=first_id)
        if since:
            updated = updated.filter(last_updated__gte=since)
        return list(updated.all()[:count])
