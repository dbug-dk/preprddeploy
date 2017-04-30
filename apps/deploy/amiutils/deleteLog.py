#!/usr/bin/python
#! coding=utf8
import getopt
import os
import glob
import shutil
import sys
import traceback
import subprocess

if __name__ == '__main__':
    opts, args = getopt.getopt(sys.argv[1:], "a:")
    for opt, arg in opts:
        if opt in ('-a'):
            homeDir = arg
            print 'try to find module dir'
            cloudDir = glob.glob('%s/cloud-*/'%homeDir)
            opsDir = '%s/cloud-ops/'%homeDir
            if opsDir in cloudDir:
                cloudDir.remove(opsDir)
            findFromDir = ' '.join(cloudDir)
            print 'search logs dir in %s'%findFromDir
            findCommand = 'find %s -name logs -type d'%findFromDir
            p = subprocess.check_output(findCommand,shell=True)
            logsDirs = p.splitlines()
            print 'delete all the logs file dir : %s'%logsDirs
            for logsDir in logsDirs:
                if os.path.exists(logsDir):
                    for path in os.listdir(logsDir):
                        absPath = os.path.join(logsDir,path)
                        if os.path.isfile(absPath):
                            print 'delete file : %s'%absPath
                            os.remove(absPath)
                        elif os.path.isdir(absPath):
                            try:
                                print 'delete dir : %s'%absPath
                                shutil.rmtree(absPath, ignore_errors=False)
                            except:
                                print 'delete dir failed,%s'%absPath
                                traceback.print_exc()
            #delete logtransfer log dir
            logtransferLogDir = os.path.join(homeDir, 'transfer_log')
            if os.path.isdir(logtransferLogDir):
                print 'delete all files in the dir: %s'%logtransferLogDir
                deleteCommand = 'rm %s/* -rf'%logtransferLogDir
                p = subprocess.Popen(deleteCommand, shell=True)
                p.communicate()
                if p.poll():
                    exit(1)
            else:
                print 'logtransfer dir not exists, create new one.'
                os.mkdir(logtransferLogDir)
            exit(0)
        else:
            print 'script run must need the arg -a xxx'
            exit(1)
    