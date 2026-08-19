from datetime import date, datetime
from typing import Protocol
from uuid import UUID

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

    def reset(self):
        ASNMap.objects.all().delete()


class IXPIdMapProjection(Projection):
    aggregate_types = [IXP.__name__]
    events = [IXPCreated.__name__]

    def do_handle(self, event: StoredEvent, aggregate: Aggregate):
        existing = IXPIdMap.objects.filter(aggregate_id=event.aggregate_id)
        if existing.count() > 0:
            return
        peeringdb_id = event.data.get("peeringdb_id", None)
        isoc_id = IXPIdMap.objects.filter(peeringdb_id=peeringdb_id).first()
        if isoc_id:
            # If an object exists, use that as it will have been pre-populated with the correct "isoc_id"
            isoc_id.aggregate_id = event.aggregate_id
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

    def reset(self):
        # This projection needs to be reset manually as we need to preserve the IXP ids
        existing = IXPIdMap.objects.exclude(
            aggregate_id__startswith="aaaabbbb-cccc-dddd-eeee-"
        )
        if existing.count() > 0:
            raise RuntimeError("You must reset IXPIdMapProjection manually")


class ASNLookup(Protocol):
    def get_asn(self, asn, as_at: datetime | None = None) -> ASN | None:
        pass


class IXPsLastUpdatedProjection(Projection):
    aggregate_types = [IXP.__name__]

    def __init__(self, app: ASNLookup):
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
        self.ixps_to_update: dict[UUID, tuple[int, dict, date]] = {}
        self.app = app

    def do_handle(self, event: StoredEvent, ixp: Aggregate):
        if not isinstance(ixp, IXP):
            return
        ids = self.id_map.find_by_peeringdb_id(ixp.peeringdb_id)
        if ids is None:
            return
        # Rather than updating the projection here we store the IXP so we can update once per import (in finalise())
        # This also overwrites anything we've previously stored for this IXP so we only update based on the latest state
        # it also means that, given we're storing the event date, we can handle multiple "imports" (i.e. rebuilding the projection from scratch)
        self.ixps_to_update[ixp.id] = (ids.pk, ixp.snapshot(), event.event_date.date())

    def ixps_updated_since(
        self, since: date | None, count: int, first_id: int
    ) -> list[UpdatedIXPs]:
        updated = UpdatedIXPs.objects.filter(isoc_id__gte=first_id)
        if since:
            updated = updated.filter(last_updated__gte=since)
        return list(updated.all()[:count])

    def finalise(self):
        for aggregate_id in self.ixps_to_update.keys():
            isoc_id, snapshot, event_date = self.ixps_to_update[aggregate_id]
            UpdatedIXPs.objects.update_or_create(
                aggregate_id=aggregate_id,
                isoc_id=isoc_id,
                defaults={
                    "last_updated": event_date,
                    "data": snapshot,
                },
            )

    def reset(self):
        UpdatedIXPs.objects.all().delete()
