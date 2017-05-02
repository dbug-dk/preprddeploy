#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views


urlpatterns = [
    url('^auto_deploy_home$', views.auto_deploy_home, name='auto_deploy_home'),
    url('^start_env_pre$', views.start_env_pre, name='start_env_pre'),
    url('^start_env', views.start_env, name='start_env'),
    url('^get_status$', views.get_status, name='get_status')
]