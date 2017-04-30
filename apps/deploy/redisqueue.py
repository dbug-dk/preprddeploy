# coding=utf8
import redis


class RedisQueue(object):
    def __init__(self, name, namespace="queue", **redis_kwargs):
        self.__db = redis.Redis(**redis_kwargs)
        self.key = '%s:%s' % (namespace, name)
        
    def qsize(self):
        return self.__db.llen(self.key)
    
    def empty(self):
        return self.qsize() == 0
    
    def put(self, item):
        self.__db.rpush(self.key, item)
    
    def get(self, block=False, timeout=None):
        if block:
            item = self.__db.blpop(self.key, timeout)
        else:
            item = self.__db.lpop(self.key)
        
        return item
    
    def get_nowait(self):
        return self.get(False)
    
    def delete_queue(self):
        self.__db.delete(self.key)
