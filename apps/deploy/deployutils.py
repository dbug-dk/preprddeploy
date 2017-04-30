#! coding=utf8
# Filename    : deployutils.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging
import os
import traceback

from django.template import Template, Context

from basicservice.models import BasicServiceDeployInfo, BasicServiceIps
from common.libs import ec2api
from common.models import AwsAccount
from deploy.templateutils import ConfTemplate, ConfigSaver
from elb.models import LoadbalancerInfo
from preprddeploy.settings import MODULE_DEPLOY_CONF_DIR, DEPLOY_BUCKET_NAME

logger = logging.getLogger('common')


def get_basic_ips(regions, account):
    basic_service_infos = {}
    for region in regions:
        logger.info('scan basic service ips in region: %s, account: %s' % (region, account))
        try:
            basic_service_instances = BasicServiceDeployInfo.find_all_instances(region, account)
        except:
            error_msg = 'get all basic service instances failed, region: %s, account: %s, error_msg:\n%s' % (
                region,
                account,
                traceback.format_exc()
            )
            raise Exception(error_msg)
        basic_services_info_in_one_region = {}
        for instance in basic_service_instances:
            instance_name = ec2api.get_instance_tag_name(instance)
            service_name = ec2api.get_module_info(instance_name)[0]
            logger.debug('found %s instance: %s' % (service_name, instance_name))
            if service_name in basic_services_info_in_one_region:
                basic_services_info_in_one_region[service_name].update({
                    instance_name: instance.private_ip_address
                })
            else:
                basic_services_info_in_one_region.update({
                    service_name: {
                        instance_name: instance.private_ip_address
                    }
                })
        logger.debug('basic service info in region(%s) and account(%s): %s' % (region,
                                                                               account,
                                                                               basic_services_info_in_one_region))
        for service_name in basic_services_info_in_one_region:
            service_infos = basic_services_info_in_one_region[service_name]
            infos_list = service_infos.items()
            infos_list.sort()
            basic_service_ips = [info[1] for info in infos_list]
            if service_name in basic_service_infos:
                basic_service_infos[service_name].update({region: basic_service_ips})
            else:
                basic_service_infos.update({
                    service_name: {region: basic_service_ips}
                })
        logger.debug('in account %s, service ip dict: %s' % (account, basic_service_infos))
    return basic_service_infos


def download_conf_template(region, module_name, module_version):
    """
    download conf template file from s3 and save template info to db.
    Args:
        region (string): region name
        module_name (string): module name
        module_version (string): module version
    """
    session = AwsAccount.get_awssession(region)
    s3res = session.resource('s3')
    s3dir = '%s/%s' % (module_name, 'config')
    conf_templates = []
    for config in ['sys', 'log4j']:
        conf_name = '%s-%s-%s' % (module_name, config, module_version)
        config_s3_path = '%s/%s' % (s3dir, conf_name)
        dest_dir = os.path.join(MODULE_DEPLOY_CONF_DIR, module_name, 'conf-template')
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
        logger.info('download %s from s3, bucket: %s, path: %s' % (
            conf_name,
            DEPLOY_BUCKET_NAME,
            config_s3_path
        ))
        conf_s3_obj = s3res.Object(DEPLOY_BUCKET_NAME, config_s3_path)
        file_path = os.path.join(dest_dir, conf_name)
        with open(file_path, 'wb') as data:
            try:
                conf_s3_obj.download_fileobj(data)
            except:
                error_msg = 'download %s from s3 failed, error msg:\n%s' % (conf_name, traceback.format_exc())
                logger.error(error_msg)
                # os.remove(file_path)
                return conf_templates
        with open(file_path, 'r') as file_reader:
            template_content = file_reader.read()
        conftemplate = ConfTemplate(module_name, config, region,
                                    template_content, module_version)
        conftemplate.save_or_update()
        conf_templates.append(conftemplate.conf_template)
    return conf_templates


def create_confs(service_names, update_versions, current_versions, regions):
    success_modules = {}
    failed_modules = {}
    diff_infos = {}
    beta_context, prd_context = BasicServiceIps.get_all_basic_ips()
    beta_elb_context = LoadbalancerInfo.get_all_elb_dns()
    for service_name, version, old_version in zip(service_names, update_versions, current_versions):
        success_modules.update({service_name: {}})
        logger.info('download templates file from s3, module: %s, version: %s' % (
            service_name,
            version,
        ))
        conftemplates = download_conf_template(regions[0], service_name, version)
        template_num = len(conftemplates)
        if template_num != 2:
            logger.error("module: %s, version: %s didn't have two conf template in s3. found %s" % (service_name,
                                                                                                    version,
                                                                                                    template_num))
            failed_modules.update({service_name: ['conf template num not correct, found %s' % template_num]})
            continue
        logger.info("download finished, start to create conf files of module: %s" % service_name)
        diff_result = []
        for conf_template in conftemplates:
            conf_name = conf_template.conf_name
            try:
                content = Template(conf_template.conf_content)
            except:
                error_msg = 'template syntax error. %s-%s\n%s' % (service_name,
                                                                  conf_name,
                                                                  traceback.format_exc())
                logger.error(error_msg)
                failed_modules.update({service_name: error_msg.splitlines()})
                continue
            for region in regions:
                beta_context.update({'region': region})
                prd_context.update({'region': region})
                beta_context = dict(beta_context, **beta_elb_context)
                logger.debug('beta context: %s' % beta_context)
                logger.debug('prd context: %s' % prd_context)
                render_beta_result = render_template(content, beta_context, region)
                if not render_beta_result['ret']:
                    failed_modules.update({service_name: render_beta_result['msg'].splitlines()})
                    break
                beta_conf_content = render_beta_result['msg']
                render_prd_result = render_template(content, prd_context, region)
                if not render_prd_result['ret']:
                    failed_modules.update({service_name: render_prd_result['msg'].splitlines()})
                    break
                prd_conf_content = render_prd_result['msg']
                module_config = ConfigSaver(service_name, conf_name, region,
                                            prd_conf_content, beta_conf_content, conf_template)
                saved_config = module_config.save()
                success_modules.get(service_name).update(saved_config)
            diff_result.append(conf_template.create_diff_file(old_version))
        diff_infos.update({service_name: diff_result})
    return success_modules, failed_modules, diff_infos


def render_template(template_content, context, region):
    try:
        rendered_text = template_content.render(Context(context))
    except:
        error_msg = 'render prd conf content failed in region: %s\n%s' % (
            region,
            traceback.format_exc()
        )
        logger.error(error_msg)
        return {'ret': False, 'msg': error_msg}
    return {'ret': True, 'msg': rendered_text}
