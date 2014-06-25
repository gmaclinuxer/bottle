'''
Created on 2013-4-21

@author: Xsank
'''

import os
import sys
import hmac
import time
import base64
import thread
import tempfile
import threading
import subprocess
import inspect
import warnings
import email.utils
import cPickle as pickle

from exception import HTTPError
from config import DEBUG


def toa(s,encode='utf-8'):
    return s.encode(encode) if isinstance(s,unicode) else str(s)


def tou(s,encode='utf-8',error='strict'):
    return s.decode(encode,error) if isinstance(s,str) else unicode(s)


def depr(message,hard=False):
    warnings.warn(message,DeprecationWarning,stacklevel=3)


def abort(code=500, text='Unknown Error: Appliction stopped.'):
    raise HTTPError(code, text)


def debug(mode=True):
    DEBUG = bool(mode)


def parse_date(ims):
    try:
        ts = email.utils.parsedate_tz(ims)
        return time.mktime(ts[:8] + (0,)) - (ts[9] or 0) - time.timezone
    except (TypeError, ValueError, IndexError):
        return None


def parse_auth(header):
    try:
        method, data = header.split(None, 1)
        if method.lower() == 'basic':
            name, pwd = base64.b64decode(data).split(':', 1)
            return name, pwd
    except (KeyError, ValueError, TypeError):
        return None


def _lscmp(a, b):
    return not sum(0 if x==y else 1 for x, y in zip(a, b)) and len(a) == len(b)


def path_shift(script_name, path_info, shift=1):
    if shift == 0: return script_name, path_info
    pathlist = path_info.strip('/').split('/')
    scriptlist = script_name.strip('/').split('/')
    if pathlist and pathlist[0] == '': pathlist = []
    if scriptlist and scriptlist[0] == '': scriptlist = []
    if shift > 0 and shift <= len(pathlist):
        moved = pathlist[:shift]
        scriptlist = scriptlist + moved
        pathlist = pathlist[shift:]
    elif shift < 0 and shift >= -len(scriptlist):
        moved = scriptlist[shift:]
        pathlist = moved + pathlist
        scriptlist = scriptlist[:shift]
    else:
        empty = 'SCRIPT_NAME' if shift < 0 else 'PATH_INFO'
        raise AssertionError("Cannot shift. Nothing left from %s" % empty)
    new_script_name = '/' + '/'.join(scriptlist)
    new_path_info = '/' + '/'.join(pathlist)
    if path_info.endswith('/') and pathlist: new_path_info += '/'
    return new_script_name, new_path_info


def cookie_encode(data, key):
    msg = base64.b64encode(pickle.dumps(data, -1))
    sig = base64.b64encode(hmac.new(key, msg).digest())
    return toa('!') + sig + toa('?') + msg


def cookie_decode(data, key):
    data = toa(data)
    if cookie_is_encoded(data):
        sig, msg = data.split(toa('?'), 1)
        if _lscmp(sig[1:], base64.b64encode(hmac.new(key, msg).digest())):
            return pickle.loads(base64.b64decode(msg))
    return None


def cookie_is_encoded(data):
    return bool(data.startswith(toa('!')) and toa('?') in data)


def yieldroutes(func):
    path = func.__name__.replace('__','/').lstrip('/')
    spec = inspect.getargspec(func)
    argc = len(spec[0]) - len(spec[3] or [])
    path += ('/:%s' * argc) % tuple(spec[0][:argc])
    yield path
    for arg in spec[0][argc:]:
        path += '/:%s' % arg
        yield path

        
def _reloader_child(server, app, interval):
    lockfile = os.environ.get('BRICK_LOCKFILE')
    bgcheck = FileCheckerThread(lockfile, interval)
    try:
        bgcheck.start()
        server.run(app)
    except KeyboardInterrupt: pass
    bgcheck.status, status = 5, bgcheck.status
    bgcheck.join() 
    if status: sys.exit(status)


def _reloader_observer(server, app, interval):
    fd, lockfile = tempfile.mkstemp(prefix='brick-reloader.', suffix='.lock')
    os.close(fd) 
    try:
        while os.path.exists(lockfile):
            args = [sys.executable] + sys.argv
            environ = os.environ.copy()
            environ['BRICK_CHILD'] = 'true'
            environ['BRICK_LOCKFILE'] = lockfile
            p = subprocess.Popen(args, env=environ)
            while p.poll() is None: 
                os.utime(lockfile, None) 
                time.sleep(interval)
            if p.poll() != 3:
                if os.path.exists(lockfile): os.unlink(lockfile)
                sys.exit(p.poll())
            elif not server.quiet:
                print "Reloading server..."
    except KeyboardInterrupt: pass
    if os.path.exists(lockfile): os.unlink(lockfile)
    

def html_escape(string):
    return string.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')\
                 .replace('"','&quot;').replace("'",'&#039;')


def html_quote(string):
    return '"%s"' % html_escape(string).replace('\n','%#10;')\
                    .replace('\r','&#13;').replace('\t','&#9;')
                    

class FileCheckerThread(threading.Thread):

    def __init__(self, lockfile, interval):
        threading.Thread.__init__(self)
        self.lockfile, self.interval = lockfile, interval
        self.status = 0

    def run(self):
        exists = os.path.exists
        mtime = lambda path: os.stat(path).st_mtime
        files = dict()
        for module in sys.modules.values():
            try:
                path = inspect.getsourcefile(module)
                if path and exists(path): files[path] = mtime(path)
            except TypeError: pass
        while not self.status:
            for path, lmtime in files.iteritems():
                if not exists(path) or mtime(path) > lmtime:
                    self.status = 3
            if not exists(self.lockfile):
                self.status = 2
            elif mtime(self.lockfile) < time.time() - self.interval - 5:
                self.status = 1
            if not self.status:
                time.sleep(self.interval)
        if self.status != 5:
            thread.interrupt_main()


class WSGIFileWrapper(object):

    def __init__(self, fp, buffer_size=1024*64):
        self.fp, self.buffer_size = fp, buffer_size
        for attr in ('fileno', 'close', 'read', 'readlines'):
            if hasattr(fp, attr): setattr(self, attr, getattr(fp, attr))

    def __iter__(self):
        read, buff = self.fp.read, self.buffer_size
        while True:
            part = read(buff)
            if not part: break
            yield part
