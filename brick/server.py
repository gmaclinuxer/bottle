'''
Created on 2013-4-21

@author: Xsank
'''

class ServerAdapter(object):
    quiet = False

    def __init__(self, host='127.0.0.1', port=8000, **kargs):
        self.options = kargs
        self.host = host
        self.port = int(port)

    def run(self, handler):
        pass
        
    def __repr__(self):
        args = ', '.join(['%s=%s'%(k,repr(v)) for k, v in self.options.items()])
        return "%s(%s)" % (self.__class__.__name__, args)
    
class WSGIRefServer(ServerAdapter):
    def run(self, handler):
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        if self.quiet:
            class QuietHandler(WSGIRequestHandler):
                #always compile error,so i insert self
                def log_request(self,*args, **kw): pass
            self.options['handler_class'] = QuietHandler
        srv = make_server(self.host, self.port, handler, **self.options)
        srv.serve_forever()