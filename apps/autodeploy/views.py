import json

import logging
import traceback

from django.forms import model_to_dict
from django.http import HttpResponse
# from django.shortcuts import render

# Create your views here.
from autodeploy import processmgr
from autodeploy.models import AutoDeployHistory
from autodeploy.processmgr import ProgressStarter
from autodeploy.upgradeinfoutils import UpgradeInfoParser
from preprddeploy.settings import AUTO_DEPLOY_PROGRESS

logger = logging.getLogger('deploy')


def start_process(request):
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
    progress = ProgressStarter(method, result_worker)
    ProgressStarter.start.delay(progress)
    return HttpResponse(json.dumps({'status': 200}))


def __get_result_worker(progress_name):
    names = [name[0].upper() + name[1:] for name in progress_name.split('_')]
    result_worker_name = '%sResultWorker' % ''.join(names)
    try:
        result_worker = getattr(processmgr, result_worker_name)
    except AttributeError:
        result_worker = getattr(processmgr, 'ResultWorker')
    return result_worker


def get_status(request):
    try:
        upgrade_version = request.GET.get('upgrade_version')
        if upgrade_version:
            deploy_history_obj = AutoDeployHistory.objects.filter(upgrade_version=upgrade_version).order_by('-start_time')[0]
        else:
            deploy_history_obj = AutoDeployHistory.objects.order_by('-start_time')[0]
        status = model_to_dict(deploy_history_obj, exclude=['task_pid', 'result_pid', 'managers'])
        progress_name = status.get('process')
        task_num = status.pop('task_num')
        current_task_name = AUTO_DEPLOY_PROGRESS[progress_name]['child_progress'][task_num]
        status.update({'current_task_name': current_task_name})
        return HttpResponse(json.dumps({'status': 200, 'msg': status}))
    except:
        return HttpResponse(json.dumps({'status': 500, 'msg': traceback.format_exc()}))
