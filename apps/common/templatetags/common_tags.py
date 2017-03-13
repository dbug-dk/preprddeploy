#! coding=utf8
# Filename    : common_tags.py
# Description : custom common template tags
# Author      : dengken
# History:
#    1.  , dengken, first create
from django import template

from apps.common.models import RegionInfo

register = template.Library()


@register.simple_tag(takes_context=True)
def current_region_cn_name(context):
    current_region = context['current_region']
    return RegionInfo.get_region_attribute(current_region, 'chinese_name')
