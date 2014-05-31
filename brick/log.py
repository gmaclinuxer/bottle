'''
Created on 2013-4-22

@author: Xsank
'''

from __future__ import absolute_import
from threading import Lock
from logging import getLogger, StreamHandler, Formatter, getLoggerClass, DEBUG

from brick.config import LOG_FILE,LOG_FORMAT,DEBUG as APP_DEBUG


_logger_lock=Lock()

class Logger(object):
    def __init__(self):
        self._logger=None
    
    @property
    def log(self):
        if self._logger and self._logger.name == self.logger_name:
            return self._logger
        with _logger_lock:
            if self._logger and self._logger.name==self.logger_name:
                return self._logger
            self._logger=create_logger(self)
            return self._logger

def create_logger(log):
    Logger=getLoggerClass()
    
    class DebugLogger(Logger):
        #always compile error,so i insert self
        def get_log_level(self,n):
            if n.level==0 and APP_DEBUG:
                return DEBUG
            return Logger.getEffectiveLevel(n)
        
    class DebugHandler(StreamHandler):
        #always compile error,so i insert self
        def emit(self,x,record):
            StreamHandler.emit(x, record) if APP_DEBUG else None
            
    
    handler=DebugHandler()
    handler.setLevel(DEBUG)
    handler.setFormatter(Formatter(LOG_FORMAT))
    logger=getLogger(LOG_FILE)
    
    del logger.handlers[:]
    logger.__class__=DebugLogger
    logger.addHandler(handler)
    return logger

