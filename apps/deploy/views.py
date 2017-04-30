# coding=utf8
import json
import logging
import os
import traceback

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django.template import Template, Context
from django.utils.datastructures import MultiValueDictKeyError

from basicservice.models import BasicServiceIps
from common.models import RegionInfo, AwsAccount
from deploy import redisqueue
from deploy.amiutils.amicreater import get_update_instances, delete_logs, create_business_amis, add_auth, clean_work
from deploy.amiutils.ec2checker import Ec2Checker
from deploy.amiutils.report import Report
from deploy.deployutils import get_basic_ips, create_confs
from deploy.htmltemplate import sorted_module_html, ami_target_html, create_ami_result_html
from deploy.scriptconfig import ScriptConfig
from deploy.scriptrunner import ServiceDeployScript
from module.models import ModuleInfo, ScriptExecLog
from permission.models import SitePage
from preprddeploy.settings import BASE_DIR

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    deploy_page = SitePage.objects.get(name='deploy')
    return render(request, 'deploy/index.html', {
        'current_region': current_region,
        'regions': regions,
        'deploy_page': deploy_page,
        'username': request.user.username
    })


def view_script_config(request):
    region_name = request.GET.get('region')
    if not region_name:
        return HttpResponse('bad request!', status=400)
    script_name = 'serviceDeploy'
    script_dirname = '%s/deploy/conf/%s' % (os.path.join(BASE_DIR, 'static'), script_name)
    script_confname = 'sys.properties_%s' % ({'cn-north-1': 'cn'}.get(region_name, 'en'))
    if not os.path.isfile(os.path.join(script_dirname, script_confname)):
        return HttpResponse('<h4 class="text-danger">can not find script conf file: %s</h4>' % script_confname)
    conf = ScriptConfig(script_name, script_confname)
    conf_contents = conf.get_content()
    return render(request, 'deploy/script-config.html', {
        'conf_contents': conf_contents,
        'script_name': script_name,
        'script_conf_name': script_confname
    })


def modify_script_conf(request):
    post_params = request.POST
    change_list = []
    script_name = ''
    script_conf_name = ''
    for key in post_params:
        if key == 'scriptName':
            script_name = post_params['scriptName']
        elif key == 'scriptConfName':
            script_conf_name = post_params['scriptConfName']
        else:
            change_list.append(post_params[key].split(';'))
    if not script_name or not script_conf_name or not change_list:
        return HttpResponse('bad request!', status=400)
    script_conf = ScriptConfig(script_name, script_conf_name)
    change_result = script_conf.modify_conf(change_list)
    return HttpResponse(json.dumps(change_result), content_type='application/json')


def get_update_modules(request):
    region_name = request.GET.get('region')
    if not region_name:
        return HttpResponse('bad request!', status=400)
    region_obj = RegionInfo.objects.get(region=region_name)
    update_modules = region_obj.moduleinfo_set.filter(~Q(update_version=u'')&~Q(update_version=None))
    update_module_infos = []
    for module in update_modules:
        module_name = module.module_name
        current_version = module.current_version
        if current_version == u'' or current_version is None:
            current_version = '-'
        update_version = module.update_version
        update_module_infos.append([module_name, current_version, update_version])
    return render(request, 'deploy/show-update-modules.html', {
        'update_module_infos': update_module_infos,
        'script_name': 'deploy'
    })


@transaction.atomic
def update_basic_ips(request):
    regions = RegionInfo.get_all_regions()
    BasicServiceIps.objects.all().delete()
    logger.info('truncate table basicserviceips table.')
    for account in ['beta', 'prd']:
        try:
            basic_service_infos = get_basic_ips(regions, account)
        except Exception as e:
            logger.error(e.message)
            return HttpResponse(e.message, status=500)
        logger.info('save ips to db, account: %s' % account)
        for service_name in basic_service_infos:
            basic_service_ips_obj = BasicServiceIps(service_name=service_name, account=account,
                                                    ips=json.dumps(basic_service_infos[service_name]))
            basic_service_ips_obj.save(True)
        logger.info('finish saving basic service ips in account: %s' % account)
    return HttpResponse('success update service ips')


def create_conf_file(request):
    try:
        module_update_infos = json.loads(request.POST['update_infos'])
        module_current_infos = json.loads(request.POST['current_infos'])
    except MultiValueDictKeyError:
        return HttpResponse('bad request!', status=400)
    except ValueError:
        return HttpResponse('collect form internal error.', status=500)
    success_modules = {}
    failed_modules = {}
    unknown_modules = []
    diff_infos = {}
    for module_name, update_version in module_update_infos.items():
        module_list = module_name.split("_")
        update_version_list = update_version.split('_')
        current_version_list = module_current_infos[module_name].split('_')
        if len(module_list) != len(update_version_list) or len(module_list) != len(current_version_list):
            return HttpResponse('module info not correct for module: %s, \
            update version: %s, current version: %s' % (
                module_name,
                update_version,
                module_current_infos[module_name]
            ), status=500)
        try:
            module_info_obj = ModuleInfo.objects.get(module_name=module_name)
        except ModuleInfo.DoesNotExist:
            unknown_modules.append(module_name)
            continue
        region_objs = module_info_obj.regions.all()
        regions = [region_obj.region for region_obj in region_objs]
        success_infos, failed_infos, diff_results = create_confs(module_list, update_version_list,
                                                                 current_version_list, regions)
        success_modules.update(success_infos)
        failed_modules.update(failed_infos)
        diff_infos.update(diff_results)
    for module, conf_info in success_modules.items():
        if not conf_info:
            success_modules.pop(module)
    logger.debug('diff result: %s' % diff_infos)
    return render(request, 'deploy/create-conf-result.html', {
        'success': success_modules,
        'fail': failed_modules,
        'unknown': unknown_modules,
        'diff_infos': diff_infos
    })


def get_script_choose_page(request):
    region = request.GET.get('region')
    script_method = request.GET.get('method')
    if not region or not script_method:
        return HttpResponse('bad request!', status=400)
    modules = ModuleInfo.objects.filter(~Q(update_version=u'') & ~Q(update_version=None))
    logger.info(modules)
    module_infos = []
    for module in modules:
        module_name = module.module_name
        current_version = module.current_version
        if current_version == u'' or current_version is None:
            current_version = '-'
        update_version = module.update_version
        module_infos.append([module_name, current_version, update_version])
    return render(request, 'deploy/script-start-page.html', {
        'module_infos': module_infos,
        'method': script_method,
    })


def get_module_sort(request):
    try:
        module_info_dict = json.loads(request.POST['module_info_dict'])
        method = request.POST['method']
    except KeyError:
        return HttpResponse('bad request!', status=400)
    except ValueError:
        return HttpResponse('module info dict not a json', status=500)
    modules = module_info_dict.keys()
    module_order_dict = {1: [], 2: [], 3: [], 4: []}
    for module in modules:
        try:
            biz_service_obj = ModuleInfo.objects.get(module_name=module).bizservicelayer_set.all()[0]
        except:
            error_msg = 'get module(%s) service layer failed\n%s' % (module, traceback.format_exc())
            logger.error(error_msg)
            return HttpResponse(error_msg, status=500)
        start_order = biz_service_obj.start_order
        module_order_dict[start_order].append(module)
    sorted_module_list = []
    for i in range(1, 5):
        sorted_module_list.extend(module_order_dict[i])
    if method == 'change' or method == 'changeback':
        sorted_module_list.reverse()
    if not sorted_module_list:
        error_msg = 'no module found in given: %s, deploy process will do nothing.' % modules
        logger.error(error_msg)
        return HttpResponse(json.dumps({
            'ret': False,
            'sorted_module_list': sorted_module_list,
            'html': '<h4>%s</h4>' % error_msg,
            'username': ''
        }))
    template = Template(sorted_module_html)
    context = Context({
        'method': method,
        'sorted_module_list': sorted_module_list,
    })
    rendered_html_content = template.render(context)
    sorted_module_list.reverse()
    return HttpResponse(json.dumps({'ret': True, 'sorted_module_list': sorted_module_list,
                                    'html': rendered_html_content}))


@login_required
def do_work_before_deploy_run(request):
    module_name = request.GET.get('module_name')
    module_version = request.GET.get('module_version')
    region = request.GET.get('region')
    method = request.GET.get('method')
    if not module_name or not module_version or not region or not method:
        return HttpResponse('bad request!', status=400)
    deploy_script = ServiceDeployScript()
    try:
        command = deploy_script.pre_work(module_name, module_version, region, method, request.user.username)
    except:
        return HttpResponse('occur error when do prework for deploy.\n%s' % traceback.format_exc(), status=500)
    return HttpResponse(command)


@login_required
def run_service_deploy(request):
    cmd = request.POST.get('command')
    username = request.user.username
    module_name = request.POST.get('module_name')
    region = request.POST.get('region')
    if not cmd or not module_name or not region:
        return HttpResponse('bad request!', status=400)
    script_obj = ServiceDeployScript()
    script_obj.run(cmd, username, region)
    return render(request, 'deploy/run-script.html', {'cmd': cmd, 'module_name': module_name})


def get_script_result(request, script_name):
    username = request.GET.get('username')
    region = request.GET.get('region')
    if not username or not region:
        return HttpResponse('bad request!', status=400)
    rq = redisqueue.RedisQueue('script_%s_%s_%s' % (script_name, region, username))
    is_end = False
    is_success = None
    result_line = rq.get(True)[1]
    if result_line == '*finished*':
        is_end = True
        is_success = True
    elif result_line.startswith('*failed*'):
        is_end = True
        is_success = False
        result_line = result_line.replace('*failed*', '')
    result_dict = {'is_end': is_end, 'is_success': is_success, 'result': result_line}
    return HttpResponse(json.dumps(result_dict))


def get_script_log(request):
    script_name = request.GET.get('script_name')
    username = request.user.username
    if not script_name or not username:
        return HttpResponse('bad request!', status=400)
    user = User.objects.get(username=username)
    try:
        script_log = ScriptExecLog.objects.filter(user=user, script_name=script_name).order_by('-exec_time')[0]
    except IndexError:
        raise HttpResponse("no script[name: %s, executor: %s] log found in the database" % (script_name, username))
    log_content = script_log.script_result
    return HttpResponse(json.dumps({'log_content': log_content}))


def get_ami_instances_info(request):
    try:
        region = request.POST['region']
        module_dict = json.loads(request.POST['module_dict'])
    except (KeyError, ValueError):
        return HttpResponse('bad request: get dest instances info', status=400)
    username = request.user.username
    if not username:
        return HttpResponse('bad request!', status=400)
    try:
        ret_dict = get_update_instances(region, module_dict, username)
        if not ret_dict['ret']:
            return HttpResponse(json.dumps({
                 'ret': False,
                 'info': {
                     'percentage': 0.2,
                     'detail': ret_dict['msg'],
                     'todo': u'获取目标主机失败,请检查模块列表'
                 }
            }))
        ret_template = Template(ami_target_html)
        context = Context({'dest_instance_info': ret_dict['dest_instance_info']})
        ret_content = ret_template.render(context)
        return HttpResponse(json.dumps({
            'ret': True,
            'info': {
                'percentage': 0.2,
                'detail': ret_content,
                'todo': u'检查实例配置...'
            },
            'module_id_dict': ret_dict['module_id_dict'],
            'username': username
        }))
    except:
        return HttpResponse(json.dumps({
            'ret': False,
            'info': {
                'percentage': 0.2,
                'detail': traceback.format_exc(),
                'todo': u'获取制作ami的目标实例时出错'
            }
        }))


def check_instances_conf(request):
    try:
        module_id_dict = json.loads(request.POST['module_id_dict'])
        region = request.POST['region']
    except (KeyError, ValueError):
        return HttpResponse('bad request: check instance conf', status=400)
    boto_session = AwsAccount.get_awssession(region)
    ec2res = boto_session.resource('ec2')
    check_instances = []
    for instance_id in module_id_dict.values():
        instance = ec2res.Instance(instance_id)
        check_instances.append(instance)
    try:
        ec2_checker = Ec2Checker(check_instances, region)
        check_result = ec2_checker.check()
        logger.debug('ec2 config check result:\n%s' % json.dumps(check_result))

        check_report = Report(check_instances, check_result)
        check_result_report = check_report.report()
        if_check_pass = check_report.pass_check(check_result)
        if if_check_pass:
            return HttpResponse(json.dumps({
                'ret': True,
                'info': {
                    'percentage': 0.4,
                    'detail': u'实例检查结果：%s' % check_result_report,
                    'todo': u'删除日志文件...'
                }
            }))
        else:
            return HttpResponse(json.dumps({
                'ret': False,
                'info': {
                    'percentage': 0.4,
                    'detail': u'实例检查结果：%s' % check_result_report,
                    'todo': u'实例检查未通过，停止创建AMI'
                }
            }))
    except:
        return HttpResponse(json.dumps({
            'ret': False,
            'info': {
                'percentage': 0.4,
                'detail': u'执行实例检查时出错:\n%s' % traceback.format_exc(),
                'todo': u'实例检查出错，停止创建AMI'
            }
        }))


def delete_module_logs(request):
    username = request.GET.get('username')
    region = request.GET.get('region')
    if not username or not region:
        return HttpResponse('bad request: delete log', status=400)
    try:
        retcode, ret_msg = delete_logs(username, region)
        return HttpResponse(json.dumps({
            'ret': retcode,
            'info': {
                'percentage': 0.6,
                'detail': ret_msg,
                'todo': u'创建AMI...' if retcode else u'删除日志出错，停止创建AMI'
            }
        }))
    except:
        return HttpResponse(json.dumps({
            'ret': False,
            'info': {
                'percentage': 0.6,
                'detail': u'批量删除实例中模块日志时出错:\n%s' % traceback.format_exc(),
                'todo': u'删除日志出错，停止创建AMI'
            }
        }))


def generate_ami(request):
    try:
        region = request.POST['region']
        module_version_dict = json.loads(request.POST['module_version_dict'])
        module_id_dict = json.loads(request.POST['module_id_dict'])
    except (KeyError, ValueError):
        return HttpResponse('bad request: generate ami', status=400)
    try:
        avail_ami_list, failed_ami_list = create_business_amis(region, module_version_dict, module_id_dict)
    except:
        return HttpResponse(json.dumps({
            'ret': False,
            'info': {
                'percentage': 0.8,
                'detail': 'occur error when creating ami and waiting it available:\n%s' % traceback.format_exc(),
                'todo': u'制作AMI时出错，停止进行AMI授权'
            },
        }))
    detail = ''
    create_success = False
    if avail_ami_list:
        create_success = True
        detail += u'<div>AMI创建成功：</div>'
        context = Context({'ami_infos': avail_ami_list})
        detail += Template(create_ami_result_html).render(context)
    if failed_ami_list:
        create_success = False
        detail += u'<div>AMI创建失败：</div>'
        context = Context({'ami_infos': failed_ami_list})
        detail += Template(create_ami_result_html).render(context)
    success_ami_info = {}
    if create_success:
        todo = u'授权prd账户'
        for ami in avail_ami_list:
            ami_module = ami[0]
            ami_id = ami[2]
            success_ami_info.update({ami_module: ami_id})
    else:
        todo = u'所有AMI都不可用，停止AMI创建'
    return HttpResponse(json.dumps({
        'ret': create_success,
        'info': {
            'percentage': 0.8,
            'detail': detail,
            'todo': todo
        },
        'success_ami': success_ami_info
    }))


def add_auth_to_prd(request):
    try:
        region = request.POST['region']
        ami_dict = json.loads(request.POST['ami_to_auth'])
    except (KeyError, ValueError):
        return HttpResponse('bad request: add auth', status=400)
    try:
        auth_success_list, auth_failed_list = add_auth(region, ami_dict)
    except:
        return HttpResponse(json.dumps({
            'ret': False,
            'info': {
                'percentage': 0.8,
                'detail': 'occur error when add ami auth to prd:\n%s' % traceback.format_exc(),
                'todo': u'授权AMI到PRD账户失败'
            },
        }))
    detail = ''
    auth_success = False
    if auth_success_list:
        auth_success = True
        detail += u'<div>授权成功：</div>'
        context = Context({'ami_infos': auth_success_list})
        detail += Template(create_ami_result_html).render(context)
    if auth_failed_list:
        detail += u'<div>授权失败:</div>'
        context = Context({'ami_infos': auth_failed_list})
        detail += Template(create_ami_result_html).render(context)
    return HttpResponse(json.dumps({
                                    'ret': auth_success,
                                    'info': {
                                            'percentage': 0.95,
                                            'detail': detail,
                                            'todo': u'清理临时文件，上传日志'
                                        }
                                }))


def do_work_after_create_ami(request):
    try:
        result = request.POST['result']
        username = request.POST['username']
        result = False if result == 'false' else True
        log_content = json.loads(request.POST['log_content'])
        region = request.POST['region']
    except KeyError, ke:
        logger.error('bad request! do_work_after_create_ami, %s' % str(ke))
        return HttpResponse('bad request!', status=400)
    clean_work(result, username, region, log_content)
    return HttpResponse('ok')
