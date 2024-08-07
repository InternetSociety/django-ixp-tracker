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
            models.UniqueConstraint(fields=['peeringdb_id'], name='unique_ixp_peeringdb_id')
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
            models.UniqueConstraint(fields=['number'], name='unique_as_number')
        ]
