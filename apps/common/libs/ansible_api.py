import logging
try:
    from ansible.runner import Runner
except ImportError:
    Runner = None  # will not run in windows

logger = logging.getLogger('common')


class AnsibleRunner(object):
    """
    This is a General object for parallel execute modules.
    """
    def __init__(self):
        self.results_raw = {}

    def run_ansible(self, module_name='shell', module_args='', ip='', keyfile='', become=False):
        """
        run module use ansible ad-hoc.
        Args:
            module_name (string): ansible module name
            module_args (string): ansible module arg
            ip (string): destination ip, if ip more than one, use comma split
            keyfile (string): ssh private key file path
            become (bool): if true, will run command in remote instance use root.
                           if false, user as same as current instance user(ubuntu).
        """
        logger.debug('execute ansible module: %s, args: %s in instances: %s' % (module_name,
                                                                                module_args,
                                                                                ip))
        hoc = Runner(module_name=module_name,
                     module_args=module_args,
                     host_list=ip.split(','),
                     private_key_file=keyfile,
                     become=become,
                     )
        self.results_raw = hoc.run()
        logger.debug('ansible results: %s' % self.results_raw)
    
    def deal_module_state_results(self):
        """
        check result when after check module state
        """
        dark = self.results_raw.get('dark')
        contacted = self.results_raw.get('contacted')
        if dark:
            return False
        if contacted:
            for host, info in contacted.items():
                rc = info.get('rc')
                if rc:
                    return False
                stdout = info.get('stdout')
                if not stdout:
                    return False
                stdout_line = stdout.split(' ')
                keyword_list = [word for word in stdout_line if word.lower() in ['no', 'not']]
                if keyword_list:
                    return False
                else:
                    return True
        else:
            return False

    @property
    def results(self):
        """
            ansibleResultRaw pattern:{'failed': {'host': 'errorMsg'}, 'ok':{'host': 'stdout'}}
        """
        result = {'failed': {}, 'ok': {}}
        # dark means remote host cannot connect
        dark_num = 0
        failed_num = 0
        success_num = 0
        dark = self.results_raw.get('dark')
        contacted = self.results_raw.get('contacted')
        if dark:
            for host, info in dark.items():
                dark_num += 1
                result['failed'][host] = info.get('msg')
        if contacted:
            for host, info in contacted.items():
                if info.get('invocation').get('module_name') in ['raw', 'shell', 'command', 'script']:
                    if info.get('rc') == 0:
                        success_num += 1
                        result['ok'][host] = info.get('stdout') + info.get('stderr')
                    else:
                        failed_num += 1
                        result['failed'][host] = info.get('stdout') + info.get('stderr')
                else:
                    if info.get('failed'):
                        failed_num += 1
                        result['failed'][host] = info.get('msg')
                    else:
                        result['ok'][host] = info.get('changed')
        total_num = dark_num + success_num + failed_num
        logger.debug('[ansible results] total: %s, not connect: %s, success: %s, failed: %s' % (
                                                                                total_num,
                                                                                dark_num,
                                                                                success_num,
                                                                                failed_num
                                                                            ))
        logger.debug('results: %s' % result)
        return result, dark_num, success_num, failed_num
