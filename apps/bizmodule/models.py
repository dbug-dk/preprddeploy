#! coding=utf8
from django.db import models

from common.models import RegionInfo
from module.models import ModuleInfo


class BizServiceLayer(models.Model):
    module = models.ForeignKey(ModuleInfo)
    service_name = models.CharField(max_length=30)
    layer_name = models.CharField(max_length=30, choices=(
        ('dataAccessLayer', u'数据访问层'),
        ('businessLayer', u'业务层'),
        ('forwardingLayer', u'转发层'),
        ('accessLayer', u'接入层')
    ))
    start_order = models.IntegerField()
    service_type = models.CharField(max_length=10)

    def __unicode__(self):
        return '%s| %s| %s' % (self.service_name, self.start_order, self.layer_name)

    @staticmethod
    def count_layer():
        biz_service_orders= BizServiceLayer.objects.all().values_list('start_order', flat=True)
        return len(set(biz_service_orders))

    @staticmethod
    def get_modules_by_layer_name(layer_name, region):
        region_obj = RegionInfo.objects.get(region=region)
        modules = region_obj.moduleinfo_set.all()
        module_names = []
        for module in modules:
            if module.bizservicelayer_set.filter(layer_name=layer_name):
                module_names.append(module.module_name)
        return module_names
