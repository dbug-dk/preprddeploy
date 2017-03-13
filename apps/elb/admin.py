from django.contrib import admin
from elb.models import *
# Register your models here.
models = [LoadbalancerInfo]
for model in models:
    admin.site.register(model)
