from django.db import models
from django.utils.translation import gettext_lazy as _


class IXP(models.Model):
    name = models.CharField(max_length=150)
    long_name = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    website = models.URLField(null=True)
    active_status = models.BooleanField(default=True)
    peeringdb_id = models.IntegerField(null=True)
    country = models.CharField(max_length=2)
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
    registration_country = models.CharField(max_length=2)
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
    member_since = models.DateField()
    last_updated = models.DateTimeField()
    is_rs_peer = models.BooleanField(default=False)
    speed = models.IntegerField(null=True)
    date_left = models.DateField(null=True)
    last_active = models.DateTimeField(null=True)

    def __str__(self):
        return self.ixp.name + " - " + self.asn.name

    class Meta:
        verbose_name = "IXP Member"
        verbose_name_plural = "IXP Members"

        constraints = [
            models.UniqueConstraint(fields=['ixp', 'asn'], name='ixp_tracker_unique_ixp_membership')
        ]
