# Generated by Django 5.0.8 on 2024-08-08 12:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ixp_tracker', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ASN',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('number', models.IntegerField()),
                ('peeringdb_id', models.IntegerField(null=True)),
                ('network_type', models.CharField(choices=[('access', 'Access'), ('transit', 'Transit'), ('content', 'Content'), ('enterprise', 'Enterprise'), ('NREN', 'Research and Education'), ('non-profit', 'Non-profit'), ('not-disclosed', 'Not Disclosed'), ('other', 'Other')], default='not-disclosed', max_length=200)),
                ('registration_country', models.CharField(max_length=2)),
                ('created', models.DateTimeField()),
                ('last_updated', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'AS Number',
                'verbose_name_plural': 'AS Numbers',
            },
        ),
        migrations.AddConstraint(
            model_name='asn',
            constraint=models.UniqueConstraint(fields=('number',), name='ixp_tracker_unique_as_number'),
        ),
    ]
