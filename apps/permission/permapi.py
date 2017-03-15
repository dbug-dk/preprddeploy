#! coding=utf8
# Filename    : permapi.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

from django.contrib.contenttypes.models import ContentType
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import get_objects_for_user
from guardian.shortcuts import get_perms_for_model

from permission.models import SitePage

logger = logging.getLogger('common')


class UserPerm(object):
    def __init__(self, user):
        self.perm_checker = ObjectPermissionChecker(user)
        self.user = user

    def get_perms_for_user(self):
        """
        return user's all permissions for all site page,
        the dict format is {permission_name: [page_names]}
        params:
            user: the django.contrib.auth.models.User object which you want get permissions
        """
        siteperms = get_perms_for_model(SitePage)
        logger.debug('site page permissions:')
        user_perms = {}
        for siteperm in siteperms:
            perm_codename = siteperm.codename
            logger.debug(perm_codename)
            perm_name = 'permission.%s' % siteperm.codename
            # get pages that user has perm ${perm_name}
            pages = get_objects_for_user(self.user, perm_name)
            if pages:
                user_perms.update({
                    perm_codename: [page.name for page in pages]
                })
        logger.debug('user permissions for site page:')
        logger.debug(json.dumps(user_perms, indent=2))
        return user_perms

    def judge_perm(self, perm_name, site_name):
        """
        check if user has perm(permName) for specify site.
        Args:
            perm_name (basestring): permission name
            site_name (basestring): site name in table SitePage
        """
        try:
            site = SitePage.objects.get(name=site_name)
        except SitePage.DoesNotExist, e:
            logger.error(e.message)
            logger.error('there is no site named %s' % site_name)
            raise
        return self.perm_checker.has_perm(perm_name, site)

    def get_objs_with_perm(self, appname, perm_name):
        """
        get models objects that self.user has perm
        Args:
            appname (basestring): app name, such as permission, module, ec2launcher and so on.
            perm_name (basestring): permission name of models
        """
        try:
            model_objects = get_objects_for_user(self.user, '%s.%s' % (appname, perm_name))
        except ContentType.DoesNotExist:
            logger.error('permission name %s not found in app: %s' % (perm_name, appname))
            raise
        return model_objects

    def get_sites_with_perm(self, perm_name):
        sites = self.get_objs_with_perm('permission', perm_name)
        site_names = [site.name for site in sites]
        return site_names
