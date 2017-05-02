#! coding=utf8
##############################################################################
# Copyright (C), 2016 , TP-LINK Technologies Co., Ltd.
# Filename    : upgradeInfoUtils.py 
# Description : parse upgrade file to get upgrade infos 
# Author      : dengken
# History:
#    1. 2017年1月17日 , dengken, first create
##############################################################################
import logging
import traceback

from django.contrib.auth.models import User

from bizmodule.models import BizServiceLayer
from common.models import RegionInfo
from module.models import ModuleInfo
from preprddeploy.settings import ACCOUNT_NAME

logger = logging.getLogger('deploy')


class UpgradeInfoParser(object):
    def __init__(self, infos_json):
        self.upgrade_content = infos_json
        self.current_regions = RegionInfo.get_all_regions()
        self.parse_list = infos_json.keys()

    def parse(self):
        results_dict = {}
        for parse_item in self.parse_list:
            parse_method_name = 'parse_%s' % parse_item
            try:
                parse_method = getattr(self, parse_method_name)
            except AttributeError:
                logger.error('no method found for parse %s' % parse_item)
                raise
            parse_result = parse_method()
            results_dict.update({parse_item: parse_result})
        return results_dict

    def parse_version(self):
        return self.upgrade_content['version']

    def parse_managers(self):
        return self.upgrade_content['managers']
    
    def parse_modules(self):
        module_infos = self.upgrade_content['modules']
        new_modules = {}
        error_modules = {}
        update_modules = []
        for module_name, module_info in module_infos.items():
            params_dict = {}
            try:
                params_dict.update({'module_name': module_name})
                params_dict.update({'current_version': module_info['current_version']})
                params_dict.update({'update_version': module_info['update_version']})
                params_dict.update({'module_type': module_info['module_type']})
                # todo: rename level, author and so on
                params_dict.update({'order': module_info['order']})
                params_dict.update({'regions': module_info['regions']})
                instance_count = module_info.get('instance_count')
                if instance_count:
                    params_dict.update({'instance_count': instance_count})
                elb_names = module_info.get('elb_names', None)
                params_dict.update({'elb_names': elb_names})
                params_dict.update({'module_layer': module_info.get('module_layer', None)})
                is_new = module_info['is_new']
                author = module_info['author']
            except KeyError as e:
                error_msg = 'key: %s not found in module info' % e.message
                logger.error(error_msg)
                error_modules.update({module_name: error_msg})
                continue
            if params_dict['current_version'] != params_dict['update_version']:
                update_modules.append((module_name, params_dict['current_version'], params_dict['update_version']))
            try:
                user = User.objects.get(username=author)
            except User.DoesNotExist:
                logger.warn('user: %s is not found, create new one with no password' % author)
                user = User.objects.create(username=author)
            params_dict.update({'user': user})
            if is_new:
                try:
                    self.__create_new_module(params_dict)
                except:
                    error_msg = 'create new module info failed.\n%s' % traceback.format_exc()
                    logger.error(error_msg)
                    error_modules.update({module_name: error_msg})
            else:
                try:
                    self.__update_module_info(params_dict)
                except:
                    error_msg = 'update module info failed. \n%s' % traceback.format_exc()
                    logger.error(error_msg)
                    error_modules.update({module_name: error_msg})
        return new_modules, error_modules, update_modules

    @staticmethod
    def __create_new_module(params_dict):
        regions = params_dict.pop('regions')
        module_type = params_dict.pop('module_type')
        module_layer = params_dict.pop('module_layer')
        if not module_layer:
            raise Exception('for new module, layer name must set.')
        module_info_obj = ModuleInfo(**params_dict)
        module_info_obj.save()
        regions_obj = RegionInfo.objects.filter(region__in=regions)
        module_name = params_dict['module_name']
        for region_obj in regions_obj:
            module_info_obj.regions.add(region_obj)
            module_info_obj.get_default_resources(module_name, region_obj.region, ACCOUNT_NAME)
        for service in module_name.split('_'):
            BizServiceLayer.save_service(module_info_obj, service, module_layer, module_type)

    @staticmethod
    def __update_module_info(params_dict):
        module_name = params_dict.pop('module_name')
        regions = params_dict.pop('regions')
        try:
            module_info = ModuleInfo.objects.get(module_name=module_name)
        except ModuleInfo.DoesNotExist:
            logger.error('module: %s not found in database.' % module_name)
            raise
        if not UpgradeInfoParser.__check_module_version(module_name, params_dict, module_info):
            error_msg = "module %s's version info is not correct!" % module_name
            logger.error(error_msg)
            raise Exception(error_msg)
        module_layer = params_dict.pop('module_layer')
        if not UpgradeInfoParser.__check_module_service(module_info, module_name, module_layer):
            error_msg = "module service info not correct."
            logger.error(error_msg)
            raise Exception(error_msg)
        UpgradeInfoParser.update_regions(module_info, regions)
        params_dict.pop('module_type')

        if params_dict['current_version'] == params_dict['update_version']:
            params_dict.update({'update_version': ''})
        for key, value in params_dict.items():
            setattr(module_info, key, value)
        module_info.save()

    @staticmethod
    def __check_module_version(module_name, params_dict, module_info):
        """
            check if module's new version is correct.
            1.new update version must not lower than new current version.
            2.new current version must exist in database after last upgrade. 
        """
        current_version = params_dict['current_version']
        update_version = params_dict['update_version']
        version_cmp_result = UpgradeInfoParser.version_cmp(update_version, current_version)
        if version_cmp_result == -1:
            logger.error("%s's update version: %s is lower than current version: %s." % (
                module_name,
                update_version,
                current_version
            ))
            return False
        else:
            version_list = []
            old_current_version = module_info.current_version
            if old_current_version:
                version_list.append(old_current_version)
            old_update_version = module_info.update_version
            if old_update_version:
                version_list.append(old_update_version)
            if current_version not in version_list:
                logger.error("%s's new current version must be one of %s, but now is %s." % (
                    module_name,
                    version_list,
                    current_version
                ))
                return False
        return True

    @staticmethod
    def update_regions(module_info_obj, regions):
        not_contains_regions = module_info_obj.regions.exclude(region__in=regions)
        if not_contains_regions:
            for region_obj in not_contains_regions:
                module_info_obj.regions.remove(region_obj)
        for region in regions:
            try:
                module_info_obj.regions.get(region=region)
            except RegionInfo.DoesNotExist:
                region_obj = RegionInfo.objects.get(region=region)
                module_info_obj.regions.add(region_obj)

    @staticmethod
    def __check_module_service(module_info_obj, module_name, module_layer):
        services = module_name.split('_')
        biz_services = module_info_obj.bizservicelayer_set.all()
        if len(biz_services) != len(services):
            logger.error('module: %s service number not correct!' % module_name)
            return False
        for service in biz_services:
            service_name = service.service_name
            if service_name not in services:
                logger.error('service: %s should not belong to module: %s' % (
                    service_name,
                    module_name
                ))
                return False
        if module_layer and biz_services[0].layer_name != module_layer:
            biz_services.update(layer_name=module_layer)
        return True

    @staticmethod
    def version_cmp(x, y):
        for version_x, version_y in zip(x.split('_'), y.split('_')):
            arr_version_x = version_x.split('.')
            arr_version_y = version_y.split('.')
            lenx = len(arr_version_x)
            leny = len(arr_version_y)
            cmp_count = min(lenx, leny)
            i = 0
            while i < cmp_count:
                try:
                    xversion = int(arr_version_x[i])
                except ValueError:
                    raise Exception('Can not parse version as integer: %s' % arr_version_x[i])
                try:
                    yversion = int(arr_version_y[i])
                except ValueError:
                    raise Exception('Can not parse version as integer: %s' % arr_version_y[i])
                if xversion < yversion:
                    return -1
                if xversion > yversion:
                    return 1
                i += 1
            if lenx > leny:
                return 1
            if lenx < leny:
                return -1
        return 0
