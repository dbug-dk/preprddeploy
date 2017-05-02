import json

import logging
import traceback
from threading import Thread

from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
# from django.shortcuts import render

# Create your views here.
from autodeploy import multiprocessmgr
from autodeploy import processmgr
from autodeploy.models import AutoDeployHistory
from autodeploy.upgradeinfoutils import UpgradeInfoParser
from preprddeploy.settings import AUTO_DEPLOY_PROGRESS

logger = logging.getLogger('deploy')


@csrf_exempt
def start_process(request):
    auto_deploy_history = AutoDeployHistory.objects.filter(Q(is_deploy_finish=False) | Q(is_result_finish=False))
    if auto_deploy_history:
        return HttpResponse('%s start process is running' % len(auto_deploy_history), status=400)
    method = request.POST.get('method')
    upgrade_infos = request.POST.get('upgrade_infos')
    if not method or not upgrade_infos:
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
    new_modules, error_modules = upgrade_info_file.parse_modules()
    if error_modules:
        # mail_sender = MailSender()
        # Thread(target=mailSender.send_mail_when_module_error,
        #        args=(error_modules, upgrade_info_json, managers)).start()
        return HttpResponse(json.dumps({'status': 500, 'info': error_modules}))
    if new_modules:
        logger.debug('new modules in this upgrade are: %s, need to check the default launch params' % new_modules)
        # mail_sender = MailSender()
        # Thread(target=mailSender.send_mail_when_new_module,
        #        args=(new_modules, managers, request.META['HTTP_HOST']))
    # start to auto deploy
    AutoDeployHistory.add_new_deploy_history(upgrade_version, managers, method)
    result_worker = __get_result_worker(method)
    progress = processmgr.ProgressStarter(method, result_worker)
    Thread(target=progress.start).start()
    return HttpResponse(json.dumps({'status': 200}))


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
