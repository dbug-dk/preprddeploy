# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('autodeploy', '0002_auto_20170410_0903'),
    ]

    operations = [
        migrations.RenameField(
            model_name='autodeployhistory',
            old_name='is_finish',
            new_name='is_deploy_finish',
        ),
        migrations.AddField(
            model_name='autodeployhistory',
            name='is_result_finish',
            field=models.BooleanField(default=False),
        ),
    ]
