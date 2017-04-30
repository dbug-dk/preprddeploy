#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views


urlpatterns = [
    url(r'^home$', views.home, name='deploy_home'),
    url(r'^view_script_config$', views.view_script_config, name='view_script_config'),
    url(r'^modify_script_conf$', views.modify_script_conf, name='modify_script_conf'),
    url(r'^get_update_modules$', views.get_update_modules, name='get_update_modules'),
    url(r'^update_basic_ips$', views.update_basic_ips, name='update_basic_ips'),
    url(r'^create_conf_file$', views.create_conf_file, name='create_conf_file'),
    url(r'^get_script_choose_page$', views.get_script_choose_page, name='get_script_choose_page'),
    url(r'^get_module_sort$', views.get_module_sort, name='get_module_sort'),
    url(r'^do_work_before_deploy_run$', views.do_work_before_deploy_run, name='do_work_before_deploy_run'),
    url(r'^run_service_deploy$', views.run_service_deploy, name='run_service_deploy'),
    url(r'^get_script_result/(?P<script_name>\w+)', views.get_script_result, name='get_script_result'),
    url(r'^get_script_log$', views.get_script_log, name='get_script_log'),
    url(r'^get_ami_instances_info$', views.get_ami_instances_info, name='get_ami_instances_info'),
    url(r'^check_instances_conf$', views.check_instances_conf, name='check_instances_conf'),
    url(r'^delete_module_logs$', views.delete_module_logs, name='delete_module_logs'),
    url(r'^generate_ami$', views.generate_ami, name='generate_ami'),
    url(r'^add_auth_to_prd$', views.add_auth_to_prd, name='add_auth_to_prd'),
    url(r'^do_work_after_create_ami$', views.do_work_after_create_ami, name='do_work_after_create_ami')
]
