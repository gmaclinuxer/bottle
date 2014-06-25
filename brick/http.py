'''
Created on 2013-4-21

@author: Xsank
'''

import cgi
from Cookie import SimpleCookie
from StringIO import StringIO
from tempfile import TemporaryFile
from urllib import quote as urlquote
from urlparse import urlunsplit,parse_qs

from structure import HeaderDict,MultiDict
from util import depr,path_shift,parse_auth,cookie_decode,cookie_encode
from config import MEMFILE_MAX


class Request(object):
    def __init__(self, environ=None, config=None):
        self.bind(environ or {}, config)

    def bind(self, environ, config=None):
        self.environ = environ
        self.config = config or {}
        self.path = '/' + environ.get('PATH_INFO', '/').lstrip('/')
        self.method = environ.get('REQUEST_METHOD', 'GET').upper()

    @property
    def _environ(self):
        depr("Request._environ renamed to Request.environ")
        return self.environ

    def copy(self):
        return Request(self.environ.copy(), self.config)
        
    def path_shift(self, shift=1):
        script_name = self.environ.get('SCRIPT_NAME','/')
        self['SCRIPT_NAME'], self.path = path_shift(script_name, self.path, shift)
        self['PATH_INFO'] = self.path

    def __getitem__(self, key): return self.environ[key]

    def __delitem__(self, key): self[key] = ""; del(self.environ[key])

    def __iter__(self): return iter(self.environ)

    def __len__(self): return len(self.environ)

    def keys(self): return self.environ.keys()

    def __setitem__(self, key, value):
        self.environ[key] = value
        todelete = []
        if key in ('PATH_INFO','REQUEST_METHOD'):
            self.bind(self.environ, self.config)
        elif key == 'wsgi.input': todelete = ('body','forms','files','params')
        elif key == 'QUERY_STRING': todelete = ('get','params')
        elif key.startswith('HTTP_'): todelete = ('headers', 'cookies')
        for key in todelete:
            if 'brick.' + key in self.environ:
                del self.environ['brick.' + key]

    @property
    def query_string(self):
        return self.environ.get('QUERY_STRING', '')

    @property
    def fullpath(self):
        return self.environ.get('SCRIPT_NAME', '').rstrip('/') + self.path

    @property
    def url(self):
        scheme = self.environ.get('wsgi.url_scheme', 'http')
        host   = self.environ.get('HTTP_X_FORWARDED_HOST', self.environ.get('HTTP_HOST', None))
        if not host:
            host = self.environ.get('SERVER_NAME')
            port = self.environ.get('SERVER_PORT', '80')
            if scheme + port not in ('https443', 'http80'):
                host += ':' + port
        parts = (scheme, host, urlquote(self.fullpath), self.query_string, '')
        return urlunsplit(parts)

    @property
    def content_length(self):
        return int(self.environ.get('CONTENT_LENGTH','') or -1)

    @property
    def header(self):
        if 'brick.headers' not in self.environ:
            header = self.environ['brick.headers'] = HeaderDict()
            for key, value in self.environ.iteritems():
                if key.startswith('HTTP_'):
                    key = key[5:].replace('_','-').title()
                    header[key] = value
        return self.environ['brick.headers']

    @property
    def GET(self):
        if 'brick.get' not in self.environ:
            data = parse_qs(self.query_string, keep_blank_values=True)
            get = self.environ['brick.get'] = MultiDict()
            for key, values in data.iteritems():
                for value in values:
                    get[key] = value
        return self.environ['brick.get']

    @property
    def POST(self):
        if 'brick.post' not in self.environ:
            self.environ['brick.post'] = MultiDict()
            self.environ['brick.forms'] = MultiDict()
            self.environ['brick.files'] = MultiDict()
            safe_env = {'QUERY_STRING':''} 
            for key in ('REQUEST_METHOD', 'CONTENT_TYPE', 'CONTENT_LENGTH'):
                if key in self.environ: safe_env[key] = self.environ[key]
            fb = self.body
            data = cgi.FieldStorage(fp=fb, environ=safe_env, keep_blank_values=True)
            for item in data.list or []:
                if item.filename:
                    self.environ['brick.post'][item.name] = item
                    self.environ['brick.files'][item.name] = item
                else:
                    self.environ['brick.post'][item.name] = item.value
                    self.environ['brick.forms'][item.name] = item.value
        return self.environ['brick.post']

    @property
    def forms(self):
        if 'brick.forms' not in self.environ: self.POST
        return self.environ['brick.forms']

    @property
    def files(self):
        if 'brick.files' not in self.environ: self.POST
        return self.environ['brick.files']
        
    @property
    def params(self):
        """ A combined MultiDict with POST and GET parameters. """
        if 'brick.params' not in self.environ:
            self.environ['brick.params'] = MultiDict(self.GET)
            self.environ['brick.params'].update(dict(self.forms))
        return self.environ['brick.params']

    @property
    def body(self):
        if 'brick.body' not in self.environ:
            maxread = max(0, self.content_length)
            stream = self.environ['wsgi.input']
            body = StringIO() if maxread < MEMFILE_MAX else TemporaryFile(mode='w+b')
            while maxread > 0:
                part = stream.read(min(maxread, MEMFILE_MAX))
                if not part:
                    break
                body.write(part)
                maxread -= len(part)
            self.environ['wsgi.input'] = body
            self.environ['brick.body'] = body
        self.environ['brick.body'].seek(0)
        return self.environ['brick.body']

    @property
    def auth(self): 
        return parse_auth(self.environ.get('HTTP_AUTHORIZATION',''))

    @property
    def COOKIES(self):
        if 'brick.cookies' not in self.environ:
            raw_dict = SimpleCookie(self.environ.get('HTTP_COOKIE',''))
            self.environ['brick.cookies'] = {}
            for cookie in raw_dict.itervalues():
                self.environ['brick.cookies'][cookie.key] = cookie.value
        return self.environ['brick.cookies']

    def get_cookie(self, name, secret=None):
        value = self.COOKIES.get(name)
        dec = cookie_decode(value, secret) if secret else None
        return dec or value

    @property
    def is_ajax(self):
        return self.header.get('X-Requested-With') == 'XMLHttpRequest'


class Response(object):
    def __init__(self, config=None):
        self.bind(config)

    def bind(self, config=None):
        self._COOKIES = None
        self.status = 200
        self.headers = HeaderDict()
        self.content_type = 'text/html; charset=UTF-8'
        self.config = config or {}

    @property
    def header(self):
        depr("Response.header renamed to Response.headers")
        return self.headers

    def copy(self):
        copy = Response(self.config)
        copy.status = self.status
        copy.headers = self.headers.copy()
        copy.content_type = self.content_type
        return copy

    def wsgiheader(self):
        for c in self.COOKIES.values():
            if c.OutputString() not in self.headers.getall('Set-Cookie'):
                self.headers.append('Set-Cookie', c.OutputString())
        if self.status in (204, 304) and 'content-type' in self.headers:
            del self.headers['content-type']
        if self.status == 304:
            for h in ('allow', 'content-encoding', 'content-language',
                      'content-length', 'content-md5', 'content-range',
                      'content-type', 'last-modified'): 
                if h in self.headers:
                    del self.headers[h]
        return list(self.headers.iterallitems())
    headerlist = property(wsgiheader)

    @property
    def charset(self):
        if 'charset=' in self.content_type:
            return self.content_type.split('charset=')[-1].split(';')[0].strip()
        return 'UTF-8'

    @property
    def COOKIES(self):
        if not self._COOKIES:
            self._COOKIES = SimpleCookie()
        return self._COOKIES

    def set_cookie(self, key, value, secret=None, **kargs):
        if not isinstance(value, basestring):
            if not secret:
                raise TypeError('Cookies must be strings when secret is not set')
            value = cookie_encode(value, secret).decode('ascii') 
        self.COOKIES[key] = value
        for k, v in kargs.iteritems():
            self.COOKIES[key][k.replace('_', '-')] = v

    def get_content_type(self):
        return self.headers['Content-Type']

    def set_content_type(self, value):
        self.headers['Content-Type'] = value

    content_type = property(get_content_type, set_content_type, None,
                            get_content_type.__doc__)



