#! coding=utf8
# Filename    : dbconn.py
# Description : when use django connect mysql, sometimes mysql server may be gone away.
#               so check connection is useable, if not useable close django db connection
# Author      : dengken
# History:
#    1.  , dengken, first create
import functools
from django.db import connection


def is_connection_usable():
    try:
        connection.connection.ping()
    except:
        return False
    else:
        return True


def check_db_connection(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not is_connection_usable():
            connection.close()
        func(*args, **kwargs)
    return wrapper
