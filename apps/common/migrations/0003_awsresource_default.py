# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_awsresource'),
    ]

    operations = [
        migrations.AddField(
            model_name='awsresource',
            name='default',
            field=models.BooleanField(default=False),
        ),
    ]
