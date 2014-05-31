'''
Created on 2013-4-21

@author: Xsank
'''

from structure import HeaderDict
from config import ERROR_PAGE_TEMPLATE

class BrickException(Exception):
    '''base class of all exception'''
    pass
    

class RouteError(BrickException):
    '''base class route_error'''
    

class RouteSyntaxError(RouteError):
    '''Route syntax error'''
    

class RouteBuildError(RouteError):
    '''Route built error'''
    
    
class RouterUnknownModeError(RouteError): 
    '''Unknown route error'''
    

class DatabaseOperationError(BrickException):
    '''database operation error'''
    
    
class HTTPResponse(BrickException):
    """ Used to break execution and immediately finish the response """
    def __init__(self, output='', status=200, header=None):
        super(BrickException, self).__init__("HTTP Response %d" % status)
        self.status = int(status)
        self.output = output
        self.headers = HeaderDict(header) if header else None

    def apply(self, response):
        if self.headers:
            for key, value in self.headers.iterallitems():
                response.headers[key] = value
        response.status = self.status


class HTTPError(HTTPResponse):
    """ Used to generate an error page """
    def __init__(self, code=500, output='Unknown Error', exception=None, traceback=None, header=None):
        super(HTTPError, self).__init__(output, code, header)
        self.exception = exception
        self.traceback = traceback

    def __repr__(self):
        from template import template
        return ''.join(template(ERROR_PAGE_TEMPLATE,e=self))
    
    
class TemplateError(HTTPError):
    def __init__(self, message):
        HTTPError.__init__(self, 500, message)

