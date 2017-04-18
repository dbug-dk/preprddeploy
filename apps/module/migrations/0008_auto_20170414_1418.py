# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0007_remove_moduleinfo_module_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='ec2optionset',
            name='name',
            field=models.CharField(default='test', max_length=100),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ec2optionset',
            name='image',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='common.AwsResource', null=True),
        ),
        migrations.AlterField(
            model_name='ec2optionset',
            name='module',
            field=models.ForeignKey(blank=True, to='module.ModuleInfo', null=True),
        ),
    ]
