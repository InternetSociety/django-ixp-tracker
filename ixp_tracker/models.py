from django.db import models
from django.utils.translation import gettext_lazy as _


class IXP(models.Model):
    name = models.CharField(max_length=150)
    long_name = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    website = models.URLField(null=True)
    active_status = models.BooleanField(default=True)
    peeringdb_id = models.IntegerField(null=True)
    country_code = models.CharField(max_length=2)
    created = models.DateTimeField()
    last_updated = models.DateTimeField()
    last_active = models.DateTimeField(null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Internet Exchange Point")
        verbose_name_plural = _("Internet Exchange Points")

        constraints = [
            models.UniqueConstraint(fields=['peeringdb_id'], name='ixp_tracker_unique_ixp_peeringdb_id')
        ]


class ASN(models.Model):
    NETWORK_TYPE_CHOICES = [
        ('access', 'Access'),
        ('transit', 'Transit'),
        ('content', 'Content'),
        ('enterprise', 'Enterprise'),
        ('NREN', 'Research and Education'),
        ('non-profit', 'Non-profit'),
        ('not-disclosed', 'Not Disclosed'),
        ('other', 'Other'),
    ]
    name = models.CharField(max_length=500)
    number = models.IntegerField()
    peeringdb_id = models.IntegerField(null=True)
    network_type = models.CharField(max_length=200, choices=NETWORK_TYPE_CHOICES, default='not-disclosed')
    registration_country_code = models.CharField(max_length=2)
    created = models.DateTimeField()
    last_updated = models.DateTimeField()

    def __str__(self):
        return "AS" + str(self.number)

    class Meta:
        verbose_name = "AS Number"
        verbose_name_plural = "AS Numbers"

        constraints = [
            models.UniqueConstraint(fields=['number'], name='ixp_tracker_unique_as_number')
        ]


class IXPMember(models.Model):
    ixp = models.ForeignKey(IXP, on_delete=models.CASCADE)
    asn = models.ForeignKey(ASN, on_delete=models.CASCADE)
    last_updated = models.DateTimeField()
    last_active = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.ixp.name} - {self.asn.name}"

    class Meta:
        verbose_name = "IXP Member"
        verbose_name_plural = "IXP Members"

        constraints = [
            models.UniqueConstraint(fields=['ixp', 'asn'], name='ixp_tracker_unique_ixp_membership')
        ]


class IXPMembershipRecord(models.Model):
    member = models.ForeignKey(IXPMember, on_delete=models.CASCADE, related_name="memberships")
    start_date = models.DateField()
    is_rs_peer = models.BooleanField(default=False)
    speed = models.IntegerField(null=True)
    end_date = models.DateField(null=True)

    def __str__(self):
        return f"Membership record {self.member} from {self.start_date} to {self.end_date}"

    class Meta:
        verbose_name = "IXP Membership record"
        verbose_name_plural = "IXP Membership records"


class StatsPerIXP(models.Model):
    ixp = models.ForeignKey(IXP, on_delete=models.CASCADE)
    stats_date = models.DateField()
    capacity = models.FloatField()
    members = models.IntegerField()
    local_asns_members_rate = models.FloatField()

    def __str__(self):
        return f"{self.ixp.name} - {self.stats_date}"

    class Meta:
        verbose_name = "IXP stats"

        constraints = [
            models.UniqueConstraint(fields=['ixp', 'stats_date'], name='ixp_tracker_unique_ixp_stats')
        ]

class StatsPerCountry(models.Model):
    country_code = models.CharField(max_length=2)
    stats_date = models.DateField()
    asn_count = models.IntegerField()
    member_count = models.IntegerField()
    asns_ixp_member_rate = models.FloatField()
    total_capacity = models.FloatField()

    def __str__(self):
        return f"{self.country_code}-{self.stats_date}-{self.asn_count}-{self.member_count}"

    class Meta:
        verbose_name = "Per-country stats"

        constraints = [
            models.UniqueConstraint(fields=['country_code', 'stats_date'], name='ixp_tracker_unique_per_country_stats')
        ]
