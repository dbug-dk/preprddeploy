import json

import logging
import traceback

import datetime
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
# from django.shortcuts import render

# Create your views here.
from autodeploy import multiprocessmgr
from autodeploy import processmgr
from autodeploy.crontask import create_task
from autodeploy.models import AutoDeployHistory
from autodeploy.upgradeinfoutils import UpgradeInfoParser
from common.models import RegionInfo
from deploy.deployutils import create_confs
from module.models import ModuleInfo
from preprddeploy.celery import app
from preprddeploy.settings import AUTO_DEPLOY_PROGRESS

logger = logging.getLogger('deploy')


@login_required
def auto_deploy_home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    autodeploy_historys = AutoDeployHistory.objects.all().order_by('-id')
    deploy_history_info = []
    for auto_deploy_history in autodeploy_historys:
        deploy_history_info.append([auto_deploy_history.id,
                                    auto_deploy_history.upgrade_version,
                                    auto_deploy_history.is_deploy_finish and auto_deploy_history.is_result_finish,
                                    auto_deploy_history.is_success,
                                    auto_deploy_history.start_time,
                                    auto_deploy_history.managers,
                                    auto_deploy_history.end_time])
    logger.debug(deploy_history_info)
    return render(request, 'autodeploy/autodeploy-index.html', locals())


@csrf_exempt
def start_env(request):
    auto_deploy_history = AutoDeployHistory.objects.filter(Q(is_deploy_finish=False) | Q(is_result_finish=False))
    if auto_deploy_history:
        return HttpResponse('%s autodeploy process is running: %s' % (
            len(auto_deploy_history),
            [history.progress_name for history in auto_deploy_history]
        ), status=400)
    upgrade_infos = request.POST.get('upgrade_infos')
    start_time = request.POST.get('start_time')
    if not upgrade_infos or not start_time:
        return HttpResponse('need process method!', status=400)
    try:
        upgrade_info_json = json.loads(upgrade_infos)
    except ValueError:
        error_msg = 'module info not a json.'
        logger.error(error_msg)
        return HttpResponse(error_msg, status=500)
    upgrade_info_file = UpgradeInfoParser(upgrade_info_json)
    managers = upgrade_info_file.parse_managers()
    upgrade_version = upgrade_info_file.parse_version()
    new_modules, error_modules, update_modules = upgrade_info_file.parse_modules()
    if error_modules:
        # mail_sender = MailSender()
        # Thread(target=mailSender.send_mail_when_module_error,
        #        args=(error_modules, upgrade_info_json, managers)).start()
        return HttpResponse(json.dumps({'status': 500, 'info': error_modules}))
    if not update_modules:
        return HttpResponse(json.dumps({'status': 500, 'info': 'no update module found'}))
    else:
        try:
            __create_conf_files(update_modules)
        except:
            return HttpResponse(json.dumps({
                'status': 500,
                'info': 'create conf for all update module failed:\n%s' % traceback.format_exc()
            }))
    if new_modules:
        logger.debug('new modules in this upgrade are: %s, need to check the default launch params' % new_modules)
        # mail_sender = MailSender()
        # Thread(target=mailSender.send_mail_when_new_module,
        #        args=(new_modules, managers, request.META['HTTP_HOST']))
    logger.info('all pre work done, add crontab task to start env')
    if create_task('start_env_at_%s' % start_time, add_start_env_crontab, {
        'upgrade_version': upgrade_version,
        'managers': managers
    }, datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M')):
        return HttpResponse(json.dumps({'status': 200}))
    return HttpResponse(json.dumps({'status': 500, 'info': 'add cronjob failed'}))


@app.task
def add_start_env_crontab(upgrade_version, managers):
    AutoDeployHistory.add_new_deploy_history(upgrade_version, managers, 'start_env')
    result_worker = __get_result_worker('start_env')
    progress = processmgr.ProgressStarter('start_env', result_worker)
    progress.start()


def __create_conf_files(update_modules):
    success_modules = {}
    failed_modules = {}
    diff_infos = {}
    for module_name, current_version, update_version in update_modules:
        module_list = module_name.split("_")
        update_version_list = update_version.split('_')
        current_version_list = current_version.split('_')
        module_info_obj = ModuleInfo.objects.get(module_name=module_name)
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
    if failed_modules:
        raise Exception('modules conf create failed, please check conf template: %s' % failed_modules)
    logger.info('all update modules conf create success.')
    return diff_infos


def __get_result_worker(progress_name):
    names = [name[0].upper() + name[1:] for name in progress_name.split('_')]
    result_worker_name = '%sResultWorker' % ''.join(names)
    try:
        result_worker = getattr(multiprocessmgr, result_worker_name)
    except AttributeError:
        result_worker = getattr(multiprocessmgr, 'ResultWorker')
    return result_worker


def get_status(request):
    try:
        upgrade_version = request.GET.get('upgrade_version')
        try:
            if upgrade_version:
                deploy_history_obj = AutoDeployHistory.objects.filter(upgrade_version=upgrade_version).order_by('-start_time')[0]
            else:
                deploy_history_obj = AutoDeployHistory.objects.order_by('-start_time')[0]
        except IndexError:
            return HttpResponse(json.dumps({'status': 500, 'msg': 'there is no history process.'}))
        progress_name = deploy_history_obj.progress_name
        start_time = deploy_history_obj.start_time
        status = {
            "log_content": deploy_history_obj.log_content,
            "upgrade_version": deploy_history_obj.upgrade_version,
            "progress_name": progress_name,
            "managers": deploy_history_obj.managers,
            "start_time": start_time.strftime('%Y:%m:%d %H:%M:%S')
        }
        is_finish = deploy_history_obj.is_deploy_finish and deploy_history_obj.is_result_finish
        status.update({'is_finish': is_finish})
        if not is_finish:
            task_num = deploy_history_obj.task_num
            current_task_name = AUTO_DEPLOY_PROGRESS[progress_name]['child_progress'][task_num-1]
            status.update({'current_task_name': current_task_name})
        else:
            end_time = deploy_history_obj.end_time
            duration = '%s seconds' % (start_time - end_time).total_seconds()
            status.update({'duration': duration})
            status.update({'end_time': end_time.strftime('%Y:%m:%d %H:%M:%S')})
            status.update({'is_success': deploy_history_obj.is_success})
        return HttpResponse(json.dumps({'status': 200, 'msg': status}))
    except:
        return HttpResponse(json.dumps({'status': 500, 'msg': traceback.format_exc()}))
