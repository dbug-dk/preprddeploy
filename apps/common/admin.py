from django.contrib import admin
from common.models import *
# Register your models here.

models = [RegionInfo, AwsAccount, AwsResource]

for model in models:
    admin.site.register(model)
