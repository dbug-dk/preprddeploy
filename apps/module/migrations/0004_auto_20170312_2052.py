# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0003_auto_20170312_2004'),
    ]

    operations = [
        migrations.AlterField(
            model_name='moduleinfo',
            name='elb_names',
            field=models.CharField(max_length=1000, null=True, blank=True),
        ),
    ]
