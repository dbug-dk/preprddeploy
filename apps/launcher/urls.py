#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url('^home$', views.home, name='launcher_home'),
    url('^update_resources$', views.update_resources, name='update_resources'),
    url('^get_resources$', views.get_resources, name='get_resources'),
    url('^create_ec2optionset$', views.create_ec2optionset, name='create_ec2optionset'),
    url('^get_ec2optionsets$', views.get_ec2optionsets, name='get_ec2optionsets'),
    url('^update_ec2optionset$', views.update_ec2optionset, name='update_ec2optionset'),
    url('^del_ec2optionset$', views.del_ec2optionset, name='del_ec2optionset'),
    url('^run_ec2optionset$', views.run_ec2optionset, name='run_ec2optionset'),
    url('^add_instance_tags', views.add_instance_tags, name='add_instance_tags'),
    url('^get_all_update_modules$', views.get_all_update_modules, name='get_all_update_modules'),
    url('^run_instances_batch$', views.run_instances_batch, name='run_instances_batch')
]
