#! coding=utf8
# Filename    : urls.py
# Description : urls file for app elb
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url(r'^home$', views.home, name='elb_home'),
    url(r'^get_loadbalancers$', views.get_loadbalancers, name='get_loadbalancers')
]
