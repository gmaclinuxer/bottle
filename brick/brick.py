'''
Created on 2013-4-21

@author: Xsank
'''

import os
import time
import itertools
import functools
import mimetypes
from json import dumps
from urlparse import urljoin
from traceback import format_exc
from types import StringType

from config import HTTP_CODES,DEBUG
from http import Request,Response
from exception import HTTPError,HTTPResponse
from router import Router
from util import depr,yieldroutes,toa,parse_date,_reloader_child,_reloader_observer
from util import WSGIFileWrapper
from server import ServerAdapter,WSGIRefServer


request = Request()
response = Response()


class Brick(object):

    def __init__(self, catchall=True, autojson=True, config=None):
        self.routes = Router()
        self._logger=None
        self.mounts = {}
        self.error_handler = {}
        self.catchall = catchall
        self.config = config or {}
        self.serve = True
        self.castfilter = []
        if autojson and dumps:
            self.add_filter(dict, dumps)

    def optimize(self, *a, **ka):
        depr("Brick.optimize() is obsolete.")

    def mount(self, app, script_path):
        if not isinstance(app, Brick):
            raise TypeError('Only Brick instances are supported for now.')
        script_path = '/'.join(filter(None, script_path.split('/')))
        path_depth = script_path.count('/') + 1
        if not script_path:
            raise TypeError('Empty script_path. Perhaps you want a merge()?')
        for other in self.mounts:
            if other.startswith(script_path):
                raise TypeError('Conflict with existing mount: %s' % other)
        @self.route('/%s/:#.*#' % script_path, method="ANY")
        def mountpoint():
            request.path_shift(path_depth)
            return app.handle(request.path, request.method)
        self.mounts[script_path] = app

    def add_filter(self, ftype, func):
        if not isinstance(ftype, type):
            raise TypeError("Expected type object, got %s" % type(ftype))
        self.castfilter = [(t, f) for (t, f) in self.castfilter if t != ftype]
        self.castfilter.append((ftype, func))
        self.castfilter.sort()

    def match_url(self, path, method='GET'):
        path, method = path.strip().lstrip('/'), method.upper()
        callbacks, args = self.routes.match(path)
        if not callbacks:
            raise HTTPError(404, "Not found: " + path)
        if method in callbacks:
            return callbacks[method], args
        if method == 'HEAD' and 'GET' in callbacks:
            return callbacks['GET'], args
        if 'ANY' in callbacks:
            return callbacks['ANY'], args
        allow = [m for m in callbacks if m != 'ANY']
        if 'GET' in allow and 'HEAD' not in allow:
            allow.append('HEAD')
        raise HTTPError(405, "Method not allowed.",
                        header=[('Allow',",".join(allow))])

    def get_url(self, routename, **kargs):
        scriptname = request.environ.get('SCRIPT_NAME', '').strip('/') + '/'
        location = self.routes.build(routename, **kargs).lstrip('/')
        return urljoin(urljoin('/', scriptname), location)

    def route(self, path=None, method='GET', **kargs):
        def wrapper(callback):
            routes = [path] if path else yieldroutes(callback)
            methods = method.split(';') if isinstance(method, str) else method
            for r in routes:
                for m in methods:
                    r, m = r.strip().lstrip('/'), m.strip().upper()
                    old = self.routes.get_route(r, **kargs)
                    if old:
                        old.target[m] = callback
                    else:
                        self.routes.add(r, {m: callback}, **kargs)
                        self.routes.compile()
            return callback
        return wrapper

    def get(self, path=None, method='GET', **kargs):
        return self.route(path, method, **kargs)

    def post(self, path=None, method='POST', **kargs):
        return self.route(path, method, **kargs)

    def put(self, path=None, method='PUT', **kargs):
        return self.route(path, method, **kargs)

    def delete(self, path=None, method='DELETE', **kargs):
        return self.route(path, method, **kargs)

    def error(self, code=500):
        def wrapper(handler):
            self.error_handler[int(code)] = handler
            return handler
        return wrapper

    def handle(self, url, method):
        if not self.serve:
            return HTTPError(503, "Server stopped")
        try:
            handler, args = self.match_url(url, method)
            return handler(**args)
        except HTTPResponse, e:
            return e
        except Exception, e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, MemoryError))\
            or not self.catchall:
                raise
            print e
            return HTTPError(500, 'Unhandled exception', e, format_exc(10))

    def _cast(self, out, request, response, peek=None):
        for testtype, filterfunc in self.castfilter:
            if isinstance(out, testtype):
                return self._cast(filterfunc(out), request, response)

        if not out:
            response.headers['Content-Length'] = 0
            return []
        if isinstance(out, (tuple, list))\
        and isinstance(out[0], (StringType, unicode)):
            out = out[0][0:0].join(out) 
        if isinstance(out, unicode):
            out = out.encode(response.charset)
        if isinstance(out, StringType):
            response.headers['Content-Length'] = str(len(out))
            return [out]
        if isinstance(out, HTTPError):
            out.apply(response)
            return self._cast(self.error_handler.get(out.status, repr)(out), request, response)
        if isinstance(out, HTTPResponse):
            out.apply(response)
            return self._cast(out.output, request, response)

        if hasattr(out, 'read'):
            if 'wsgi.file_wrapper' in request.environ:
                return request.environ['wsgi.file_wrapper'](out)
            elif hasattr(out, 'close') or not hasattr(out, '__iter__'):
                return WSGIFileWrapper(out)

        try:
            out = iter(out)
            first = out.next()
            while not first:
                first = out.next()
        except StopIteration:
            return self._cast('', request, response)
        except HTTPResponse, e:
            first = e
        except Exception, e:
            first = HTTPError(500, 'Unhandled exception', e, format_exc(10))
            if isinstance(e, (KeyboardInterrupt, SystemExit, MemoryError))\
            or not self.catchall:
                raise
        if isinstance(first, HTTPResponse):
            return self._cast(first, request, response)
        if isinstance(first, StringType):
            return itertools.chain([first], out)
        if isinstance(first, unicode):
            return itertools.imap(lambda x: x.encode(response.charset),
                                  itertools.chain([first], out))
        return self._cast(HTTPError(500, 'Unsupported response type: %s'\
                                         % type(first)), request, response)

    def __call__(self, environ, start_response):
        try:
            environ['brick.app'] = self
            request.bind(environ)
            response.bind(self)
            #handle do something error,the out get nothing
            out = self.handle(request.path, request.method)
            out = self._cast(out, request, response)
            if response.status in (100, 101, 204, 304) or request.method == 'HEAD':
                out = []
            status = '%d %s' % (response.status, HTTP_CODES[response.status])
            start_response(status, response.headerlist)
            return out
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
        except Exception, e:
            if not self.catchall:
                raise
            err = '<h1>Critical error while processing request: %s</h1>' \
                  % environ.get('PATH_INFO', '/')
            if DEBUG:
                err += '<h2>Error:</h2>\n<pre>%s</pre>\n' % repr(e)
                err += '<h2>Traceback:</h2>\n<pre>%s</pre>\n' % format_exc(10)
            environ['wsgi.errors'].write(err) 
            start_response('500 INTERNAL SERVER ERROR', [('Content-Type', 'text/html')])
            return [toa(err)]

        
def run(app=None, server=WSGIRefServer, host='127.0.0.1', port=8000,
        interval=1, reloader=False, quiet=False, **kargs):
    app = app if app else default_app()
    if isinstance(server, type):
        server = server(host=host, port=port, **kargs)
    if not isinstance(server, ServerAdapter):
        raise RuntimeError("Server must be a subclass of WSGIAdapter")
    server.quiet = server.quiet or quiet
    if not server.quiet and not os.environ.get('BRICK_CHILD'):
        print "brick server starting up (using %s)..." % repr(server)
        print "Listening on http://%s:%d/" % (server.host, server.port)
        print "Use Ctrl-C to quit."
        print
    try:
        if reloader:
            interval = min(interval, 1)
            if os.environ.get('BRICK_CHILD'):
                _reloader_child(server, app, interval)
            else:
                _reloader_observer(server, app, interval)
        else:
            server.run(app)
    except KeyboardInterrupt: pass
    if not server.quiet and not os.environ.get('BRICK_CHILD'):
        print "Shutting down..."

        
def redirect(url, code=303):
    scriptname = request.environ.get('SCRIPT_NAME', '').rstrip('/') + '/'
    location = urljoin(request.url, urljoin(scriptname, url))
    raise HTTPResponse("", status=code, header=dict(Location=location))


def send_file(*a, **k):
    raise static_file(*a, **k)


def static_file(filename, root, guessmime=True, mimetype=None, download=False):
    root = os.path.abspath(root) + os.sep
    filename = os.path.abspath(os.path.join(root, filename.strip('/\\')))
    header = dict()

    if not filename.startswith(root):
        return HTTPError(403, "Access denied.")
    if not os.path.exists(filename) or not os.path.isfile(filename):
        return HTTPError(404, "File does not exist.")
    if not os.access(filename, os.R_OK):
        return HTTPError(403, "You do not have permission to access this file.")

    if not mimetype and guessmime:
        header['Content-Type'] = mimetypes.guess_type(filename)[0]
    else:
        header['Content-Type'] = mimetype if mimetype else 'text/plain'

    if download == True:
        download = os.path.basename(filename)
    if download:
        header['Content-Disposition'] = 'attachment; filename="%s"' % download

    stats = os.stat(filename)
    lm = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(stats.st_mtime))
    header['Last-Modified'] = lm
    ims = request.environ.get('HTTP_IF_MODIFIED_SINCE')
    if ims:
        ims = ims.split(";")[0].strip() 
        ims = parse_date(ims)
        if ims is not None and ims >= int(stats.st_mtime):
            header['Date'] = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
            return HTTPResponse(status=304, header=header)
    header['Content-Length'] = stats.st_size
    if request.method == 'HEAD':
        return HTTPResponse('', header=header)
    else:
        return HTTPResponse(open(filename, 'rb'), header=header)


class AppStack(list):

    def __call__(self):
        return self[-1]

    def push(self, value=None):
        if not isinstance(value, Brick):
            value = Brick()
        self.append(value)
        return value          

app = default_app = AppStack()
app.push()
            

route  = functools.wraps(Brick.route)(lambda *a, **ka: app().route(*a, **ka))
get    = functools.wraps(Brick.get)(lambda *a, **ka: app().get(*a, **ka))
post   = functools.wraps(Brick.post)(lambda *a, **ka: app().post(*a, **ka))
put    = functools.wraps(Brick.put)(lambda *a, **ka: app().put(*a, **ka))
delete = functools.wraps(Brick.delete)(lambda *a, **ka: app().delete(*a, **ka))
error  = functools.wraps(Brick.error)(lambda *a, **ka: app().error(*a, **ka))
url    = functools.wraps(Brick.get_url)(lambda *a, **ka: app().get_url(*a, **ka))
mount  = functools.wraps(Brick.mount)(lambda *a, **ka: app().mount(*a, **ka))     