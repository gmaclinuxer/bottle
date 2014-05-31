'''
Created on 2013-4-21

@author: Xsank
'''

import re

from exception import RouteError,RouteBuildError,RouteSyntaxError

class Route(object):
    syntax = re.compile(r'(.*?)(?<!\\):([a-zA-Z_]+)?(?:#(.*?)#)?')
    default = '[^/]+'

    def __init__(self, route, target=None, name=None, static=False):
        self.route = route
        self.target = target
        self.name = name
        if static:
            self.route = self.route.replace(':','\\:')
        self._tokens = None

    def tokens(self):
        if not self._tokens:
            self._tokens = list(self.tokenise(self.route))
        return self._tokens

    @classmethod
    def tokenise(cls, route):
        match = None
        for match in cls.syntax.finditer(route):
            pre, name, rex = match.groups()
            if pre: yield ('TXT', pre.replace('\\:',':'))
            if rex and name: yield ('VAR', (rex, name))
            elif name: yield ('VAR', (cls.default, name))
            elif rex: yield ('ANON', rex)
        if not match:
            yield ('TXT', route.replace('\\:',':'))
        elif match.end() < len(route):
            yield ('TXT', route[match.end():].replace('\\:',':'))

    def group_re(self):
        out = ''
        for token, data in self.tokens():
            if   token == 'TXT':  out += re.escape(data)
            elif token == 'VAR':  out += '(?P<%s>%s)' % (data[1], data[0])
            elif token == 'ANON': out += '(?:%s)' % data
        return out

    def flat_re(self):
        rf = lambda m: m.group(0) if len(m.group(1)) % 2 else m.group(1) + '(?:'
        return re.sub(r'(\\*)(\(\?P<[^>]*>|\((?!\?))', rf, self.group_re())

    def format_str(self):
        out, i = '', 0
        for token, value in self.tokens():
            if token == 'TXT': out += value.replace('%','%%')
            elif token == 'ANON': out += '%%(anon%d)s' % i; i+=1
            elif token == 'VAR': out += '%%(%s)s' % value[1]
        return out

    @property
    def static(self):
        return not self.is_dynamic()

    def is_dynamic(self):
        #if i remove the value,would it go wrong?
        for token in self.tokens():
            if token != 'TXT':
                return True
        return False

    def __repr__(self):
        return "<Route(%s) />" % repr(self.route)

    def __eq__(self, other):
        return self.route == other.route

class Router(object):

    def __init__(self):
        self.routes  = [] 
        self.named   = {}  
        self.static  = {} 
        self.dynamic = []  

    def add(self, route, target=None, **ka):
        if not isinstance(route, Route):
            route = Route(route, target, **ka)
        if self.get_route(route):
            return RouteError('Route %s is not uniqe.' % route)
        self.routes.append(route)
        return route

    def get_route(self, route, target=None, **ka):
        if not isinstance(route, Route):
            route = Route(route, **ka)
        for known in self.routes:
            if route == known:
                return known
        return None

    def match(self, uri):
        if uri in self.static:
            return self.static[uri], {}
        for combined, subroutes in self.dynamic:
            match = combined.match(uri)
            if not match: continue
            target, args_re = subroutes[match.lastindex - 1]
            args = args_re.match(uri).groupdict() if args_re else {}
            return target, args
        return None, {}

    def build(self, _name, **args):
        try:
            return self.named[_name] % args
        except KeyError:
            raise RouteBuildError("No route found with name '%s'." % _name)

    def compile(self):
        self.named = {}
        self.static = {}
        self.dynamic = []
        for route in self.routes:
            if route.name:
                self.named[route.name] = route.format_str()
            if route.static:
                self.static[route.route] = route.target
                continue
            gpatt = route.group_re()
            fpatt = route.flat_re()
            try:
                gregexp = re.compile('^(%s)$' % gpatt) if '(?P' in gpatt else None
                combined = '%s|(^%s$)' % (self.dynamic[-1][0].pattern, fpatt)
                self.dynamic[-1] = (re.compile(combined), self.dynamic[-1][1])
                self.dynamic[-1][1].append((route.target, gregexp))
            except (AssertionError, IndexError), e: # AssertionError: Too many groups
                self.dynamic.append((re.compile('(^%s$)'%fpatt),[(route.target, gregexp)]))
            except re.error, e:
                raise RouteSyntaxError("Could not add Route: %s (%s)" % (route, e))

    def __eq__(self, other):
        return self.routes == other.routes
