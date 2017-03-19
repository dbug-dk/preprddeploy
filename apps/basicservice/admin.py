from django.contrib import admin
from basicservice.models import *
# Register your models here.

models = [BasicServiceDeployInfo]
for model in models:
    admin.site.register(model)
