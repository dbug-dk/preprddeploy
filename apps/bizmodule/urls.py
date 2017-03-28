#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url(r'^home$', views.home, name='bizmodule_home'),
    url(r'^show_instances$', views.show_instances, name='show_instances'),
    url(r'^check_biz_state$', views.check_biz_state, name='check_biz_state'),
    url(r'^start_service$', views.start_service, name='start_service')
]
