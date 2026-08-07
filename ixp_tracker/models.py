from django.db import models

from ixp_tracker.json import IXPJSONEncoder


class StatsPerIXP(models.Model):
    ixp = models.IntegerField()  # The ISOC id
    stats_date = models.DateField()
    capacity = models.FloatField()
    members = models.IntegerField()
    domestic_network_membership = models.FloatField()
    domestic_network_coverage = models.FloatField()  # renamed
    rs_peering_rate = models.FloatField()
    members_joined_last_12_months = models.IntegerField()
    members_left_last_12_months = models.IntegerField()
    monthly_members_change = models.IntegerField()
    monthly_members_change_percent = models.FloatField()
    last_generated = models.DateTimeField()

    def __str__(self):
        return f"{self.ixp} - {self.stats_date}"

    class Meta:
        verbose_name = "IXP stats"

        constraints = [
            models.UniqueConstraint(
                fields=["ixp", "stats_date"], name="ixp_tracker_es_unique_ixp_stats"
            )
        ]


class StatsPerCountry(models.Model):
    country_code = models.CharField(max_length=2)
    stats_date = models.DateField()
    ixp_count = models.IntegerField()
    routed_asn_count = models.IntegerField()
    member_count = models.IntegerField()
    domestic_network_membership = models.FloatField()
    domestic_network_coverage = models.FloatField()
    total_capacity = models.FloatField()
    last_generated = models.DateTimeField()

    def __str__(self):
        return f"{self.country_code}-{self.stats_date}-{self.routed_asn_count}-{self.member_count}"

    class Meta:
        verbose_name = "Per-country stats"

        constraints = [
            models.UniqueConstraint(
                fields=["country_code", "stats_date"],
                name="ixp_tracker_unique_per_country_stats_es",
            )
        ]


class CannotChangeStoredEvent(Exception):
    pass


class StoredEvent(models.Model):
    aggregate_id = models.UUIDField()
    aggregate_type = models.TextField(blank=False)
    event_date = models.DateTimeField()
    event_type = models.TextField(blank=False)
    event_sequence = models.IntegerField()
    data = models.JSONField(encoder=IXPJSONEncoder)

    def __str__(self):
        return f"{self.aggregate_id}-{self.event_sequence}-{self.event_type}"

    class Meta:
        verbose_name = "Stored event"

        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_id", "event_sequence"],
                name="ixp_tracker_aggregate_sequence",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise CannotChangeStoredEvent
        super().save(*args, **kwargs)


class IXPIdMap(models.Model):
    aggregate_id = models.UUIDField()
    peeringdb_id = models.IntegerField(null=True)

    def __str__(self):
        return f"{self.aggregate_id}, ISOC id: {self.id}, PDB id: {self.peeringdb_id}"

    class Meta:
        verbose_name = "ISOC id mapping"

        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_id"], name="ixp_tracker_aggregate_isoc_id"
            ),
            models.UniqueConstraint(
                fields=["peeringdb_id"], name="ixp_tracker_aggregate_peeringdb_id"
            ),
        ]


class ASNMap(models.Model):
    aggregate_id = models.UUIDField()
    asn = models.IntegerField()

    def __str__(self):
        return f"{self.aggregate_id}, ASN: {self.asn}"

    class Meta:
        verbose_name = "ASN mapping"

        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_id"], name="ixp_tracker_asn_map_aggregate_id"
            ),
            models.UniqueConstraint(fields=["asn"], name="ixp_tracker_asn_map_asn"),
        ]


class AggregateSnapshot(models.Model):
    aggregate_id = models.UUIDField()
    event_sequence = models.IntegerField()
    snapshot_date = models.DateTimeField()
    data = models.JSONField(encoder=IXPJSONEncoder)

    def __str__(self):
        return f"Snapshot for {self.aggregate_id} ({self.event_sequence})"

    class Meta:
        verbose_name = "Aggregate snapshot"
        ordering = ["-event_sequence"]

        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_id", "event_sequence"],
                name="ixp_tracker_snapshot_aggregate_sequence",
            )
        ]


class UpdatedIXPs(models.Model):
    aggregate_id = models.UUIDField()
    last_updated = (
        models.DateField()
    )  # We only need the date here as that simplifies querying.
    isoc_id = models.IntegerField()
    data = models.JSONField(encoder=IXPJSONEncoder)

    def __str__(self):
        return (
            f"IXP {self.aggregate_id} ({self.isoc_id}) last updated {self.last_updated}"
        )

    class Meta:
        verbose_name = "Last updated IXPs"
        ordering = ["isoc_id"]

        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_id"],
                name="ixp_tracker_last_updated_ixps",
            )
        ]
