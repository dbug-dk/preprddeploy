#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url(r'^home$', views.home, name='basic_home'),
    url(r'^start_basic_service$', views.start_basic_service, name='start_basic_service'),
    url(r'^stop_basic_service$', views.stop_basic_service, name='stop_basic_service'),
    url(r'^check_basic_service$', views.check_basic_service, name='check_basic_service')
]
