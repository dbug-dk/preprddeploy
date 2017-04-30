#! coding=utf8
import json
import logging
import os
import stat
import time
import traceback

from django.contrib.auth.models import User

from common.libs import ec2api
from common.libs.ansible_api import AnsibleRunner
from common.models import AwsAccount, RegionInfo
from module.models import ScriptExecLog
from preprddeploy.settings import HOME_PATH, KEY_PATH

logger = logging.getLogger('common')
PWD = os.path.split(os.path.realpath(__file__))[0]


def get_update_instances(region, update_module_info, current_username):
    """
    choose instances to create ami base on update-module list
    generate a hosts file: ../hosts
    Args:
        region: specify region where to scan instances
        update_module_info : dict of updated module's name and version
        current_username: username
    return : dict, if success, {'ret': True, 'dest_instance_info': xxx, 'module_id_dict': xxx}
                   else: {'ret': False, 'msg': 'xxxx'}
    """
    logger.info('----------start----------')
    logger.info('get instances which will create business AMIs...')
    instances = ec2api.find_instances(region, ['*'], is_running=True)
    ret_dict = _get_dest_instance_info(instances, update_module_info)
    if not ret_dict['ret']:
        return ret_dict
    checked_list = []
    check_key_failed_list = []
    dest_instance_info = ret_dict['dest_instance_info']
    try:
        with open('hosts_%s_%s' % (current_username, region), 'w') as fp:
            for instance_id, ip, key, module in dest_instance_info:
                if key not in checked_list:
                    pass_check, key_info = _check_key_info(key)
                    if not pass_check:
                        check_key_failed_list.append(key + '.pem')
                    else:
                        fp.write('%s ansible_ssh_private_key_file=%s\n' % (ip, key_info))
    except:
        error_msg = 'occur error when write hosts file:\n%s' % traceback.format_exc()
        logger.error(error_msg)
        return {'ret': False, 'msg': error_msg}
    if check_key_failed_list:
        error_msg = 'these private key file check not pass(non exist or chmod failed): %s' % check_key_failed_list
        logger.error(error_msg)
        return {'ret': False, 'msg': error_msg}
    logger.debug('instances will be chose to create AMI are:\n%s' % dest_instance_info)
    return ret_dict


def _get_dest_instance_info(instances, update_module_info):
    """
    return instances' infomation include instance id, private ip, keypair name and module name.
    """
    dest_instance_info = []
    module_to_instance_id = {}
    for instance in instances:
        instance_name = ec2api.get_instance_tag_name(instance)
        if not instance_name:
            continue
        module_name, module_version = ec2api.get_module_info(instance_name)
        if module_name in update_module_info and module_version == update_module_info.get(module_name):
            instance_id = instance.instance_id
            instance_ip = instance.private_ip_address
            keyname = instance.key_name
            dest_instance_info.append((instance_id, instance_ip, keyname, module_name))
            update_module_info.pop(module_name)
            module_to_instance_id.update({module_name: instance_id})
    if update_module_info:
        error_msg = "some modules' instance not found : %s" % update_module_info.keys()
        logger.error(error_msg)
        return {'ret': False, 'msg': error_msg}
    return {'ret': True, 'dest_instance_info': dest_instance_info, 'module_id_dict': module_to_instance_id}


def _check_key_info(keyname):
    key_file_path = '%s/%s.pem' % (KEY_PATH, keyname)
    logger.debug('check private key [%s] in [%s]' % (keyname, KEY_PATH))
    if not os.path.isfile(key_file_path):
        logger.error('key not found: %s' % key_file_path)
        return False, "key not found"
    else:
        file_st_mode = oct(os.stat(key_file_path).st_mode)[-3:]
        if file_st_mode != '600' and file_st_mode != '400':
            logger.info('%s exists, but its permission is %s. try to fix to 600' % (
                keyname,
                file_st_mode
            ))
            try:
                os.chmod(key_file_path, stat.S_IREAD | stat.S_IWRITE)
            except Exception, e:
                logger.error('change file permission to 600 failed: %s' % e.message)
                return False, "auth change failed"
    return True, key_file_path


def delete_logs(username, region):
    """
    delete all the log files
    Args:
        username (string): username
        region (string): region name
    """
    ansible_runner = AnsibleRunner()
    ansible_runner.run_ansible(module_name='script', module_args='%s/deletelog.py -a %s' % (PWD, HOME_PATH),
                               hosts_file='hosts_%s_%s' % (username, region))
    results = ansible_runner.results
    if results[1] + results[3]:
        error_msg = 'occur errors when delete logs. error msg:\n%s' % results[0]['failed']
        logger.error(error_msg)
        return False, error_msg
    else:
        logger.info('delete logs success.')
        return True, u'删除日志完成.'


def create_business_amis(region, module_version_dict, module_id_dict):
    """
    create amis
    Args:
        region (string): region to create ami
        module_version_dict (dict): module name to version dict
        module_id_dict (dict): module name and instance id
    Returns:
        image list each items contains module name and image object
    """
    image_list = []
    boto_session = AwsAccount.get_awssession(region)
    ec2res = boto_session.resource('ec2')
    for module in module_version_dict:
        module_version = module_version_dict.get(module)
        image_name = _get_image_name(region, module, module_version)
        instance_id = module_id_dict.get(module)
        image = create_ami(ec2res, instance_id, image_name)
        # make sure the ami has already created.
        while True:
            try:
                image.load()
                break
            except:
                pass
        logger.info("finish creating %s'ami, its name is %s, id is %s, wait its state change to available." % (
            module,
            image.name,
            image.image_id
        ))
        image_list.append((module, image))
    logger.info('all amis have created, waiting to be available')
    avail_ami_list, failed_ami_list = wait_ami_available(image_list)
    if failed_ami_list:
        logger.error('some ami create failed: %s' % failed_ami_list)
    return avail_ami_list, failed_ami_list


def create_ami(ec2res, instance_id, image_name):
    """
    stop the instance and create an AMI.
    Args:
        ec2res: ec2 resource object
        instance_id (string): the instance's id to create an AMI
        image_name (string): ami's name
    Returns:
        (Ec2.Image) created image object
    """
    instance = ec2res.Instance(instance_id)
    logger.info('start to create ami: %s' % image_name)
    return instance.create_image(Name=image_name, NoReboot=False)


def wait_ami_available(image_list):
    available_list = []
    failed_list = []
    while image_list:
        for module_name, image in image_list:
            image_name = image.name
            image_id = image.image_id
            image.load()
            image_state = image.state
            if image_state == 'available':
                available_list.append((module_name, image_name, image_id))
                image_list.remove((module_name, image))
            elif image_state == 'failed':
                failed_list.append((module_name, image_name, image_id))
                image_list.remove((module_name, image))
            else:
                time.sleep(1)
    return available_list, failed_list


def add_auth(region, ami_dict):
    success_list = []
    failed_list = []
    prd_account = _get_prd_account_id(region)
    boto_session = AwsAccount.get_awssession(region)
    ec2resource = boto_session.resource('ec2')
    for module_name in ami_dict:
        image_id = ami_dict.get(module_name)
        image = ec2resource.Image(image_id)
        image_name = image.name
        response = image.modify_attribute(
            LaunchPermission={
                'Add': [
                    {
                        'UserId': prd_account
                    }
                ]
            })
        if response.get('ResponseMetadata').get('HTTPStatusCode') != 200:
            logger.error("error when add %s's launch permission to prd account: %s" % (image_name,
                                                                                       prd_account))
            failed_list.append(module_name, image_name, image_id)
        else:
            logger.info("ami: %s's creating work done." % image_name)
            success_list.append((module_name, image_name, image_id))
    return success_list, failed_list


def _get_prd_account_id(region):
    env = 'cn' if region == 'cn-north-1' else 'en'
    account_obj = AwsAccount.objects.get(name='%s-prd' % env)
    return account_obj.account_id


def clean_work(result, username, region, log_content):
    _delete_hosts_file(username, region)
    _save_ami_logs(result, username, log_content)


def _delete_hosts_file(username, region):
    hosts_file = 'hosts_%s_%s' % (username, region)
    if os.path.isfile(hosts_file):
        try:
            os.remove(hosts_file)
            logger.debug('delete the tmp hosts file')
        except Exception, e:
            logger.error('occur errors when delete file: %s, reason: %s' % (hosts_file,
                                                                            str(e)
                                                                            ))
    else:
        logger.info("the tmp hosts file haven't create. don't need to delete")


def _save_ami_logs(result, username, log_content):
    if result:
        logger.debug('create ami done.')
    else:
        logger.error('create ami failed, abort.')
    exec_user = User.objects.get(username=username)
    log_details = log_content['details']
    dest_module_infos = log_content['module_version_dict']
    script_exec_log = ScriptExecLog(user=exec_user, script_name='amiTools',
                                    script_content=dest_module_infos, if_success=result,
                                    script_result=log_details)
    script_exec_log.save()


def _get_image_name(region, module_name, module_version):
    region_abbr = RegionInfo.objects.get(region=region).abbr
    current_time = time.strftime("%Y%m%d", time.localtime())
    image_name = '-'.join(['preprd', 'ami', module_name,
                           module_version, region_abbr, current_time])
    return image_name
