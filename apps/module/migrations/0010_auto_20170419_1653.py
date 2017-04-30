# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0009_remove_moduleinfo_elb_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ec2optionset',
            name='name',
            field=models.CharField(unique=True, max_length=100),
        ),
    ]
