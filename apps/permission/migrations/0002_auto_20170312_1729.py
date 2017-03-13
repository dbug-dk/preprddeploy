# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('permission', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitepage',
            name='name',
            field=models.CharField(max_length=50, choices=[(b'permission', '\u7528\u6237\u9a8c\u8bc1\u4e0e\u6743\u9650\u7ba1\u7406'), (b'module', '\u6a21\u5757\u7248\u672c\u7ba1\u7406')]),
        ),
    ]
