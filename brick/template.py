'''
Created on 2013-4-21

@author: Xsank
'''

import os
import re
import tokenize

from exception import TemplateError
from util import tou,abort,html_escape
from config import TEMPLATES,TEMPLATE_PATH,DEBUG

class BaseTemplate(object):
    extentions = ['tpl','html']
    settings = {}
    defaults = {} 

    def __init__(self, source=None, name=None, lookup=[], encoding='utf8', **settings):
        self.name = name
        self.source = source.read() if hasattr(source, 'read') else source
        self.filename = source.filename if hasattr(source, 'filename') else None
        self.lookup = map(os.path.abspath, lookup)
        self.encoding = encoding
        self.settings = self.settings.copy() 
        self.settings.update(settings) 
        if not self.source and self.name:
            self.filename = self.search(self.name, self.lookup)
            if not self.filename:
                raise TemplateError('Template %s not found.' % repr(name))
        if not self.source and not self.filename:
            raise TemplateError('No template specified.')
        self.prepare(**self.settings)

    @classmethod
    def search(cls, name, lookup=[]):
        if os.path.isfile(name): return name
        for spath in lookup:
            fname = os.path.join(spath, name)
            if os.path.isfile(fname):
                return fname
            for ext in cls.extentions:
                if os.path.isfile('%s.%s' % (fname, ext)):
                    return '%s.%s' % (fname, ext)

    @classmethod
    def global_config(cls, key, *args):
        if args:
            cls.settings[key] = args[0]
        else:
            return cls.settings[key]

    def prepare(self, **options):
        raise NotImplementedError

    def render(self, **args):
        raise NotImplementedError
    
    
class SimpleTemplate(BaseTemplate):
    blocks = ('if','elif','else','try','except','finally','for','while','with','def','class')
    dedent_blocks = ('elif', 'else', 'except', 'finally')

    def prepare(self, escape_func=html_escape, noescape=False):
        self.cache = {}
        if self.source:
            self.code = self.translate(self.source)
            self.co = compile(self.code, '<string>', 'exec')
        else:
            self.code = self.translate(open(self.filename).read())
            self.co = compile(self.code, self.filename, 'exec')
        enc = self.encoding
        self._str = lambda x: tou(x, enc)
        #use html escape ,but something infect did wrong
        #self._escape = lambda x: escape_func(tou(x, enc))
        self._escape=lambda x:tou(x,enc)
        if noescape:
            self._str, self._escape = self._escape, self._str

    def translate(self, template):
        stack = [] 
        lineno = 0 
        ptrbuffer = [] 
        codebuffer = [] 
        oneline=multiline = dedent = False

        def yield_tokens(line):
            for i, part in enumerate(re.split(r'\{\{(.*?)\}\}', line)):
                if i % 2:
                    if part.startswith('!'): yield 'RAW', part[1:]
                    else: yield 'CMD', part
                else: yield 'TXT', part

        def split_comment(codeline):
            line = codeline.splitlines()[0]
            try:
                tokens = list(tokenize.generate_tokens(iter(line).next))
            except tokenize.TokenError:
                return line.rsplit('#',1) if '#' in line else (line, '')
            for token in tokens:
                if token[0] == tokenize.COMMENT:
                    start, end = token[2][1], token[3][1]
                    return codeline[:start] + codeline[end:], codeline[start:end]
            return line, ''

        def flush(): 
            if not ptrbuffer: return
            cline = ''
            for line in ptrbuffer:
                for token, value in line:
                    if token == 'TXT': cline += repr(value)
                    elif token == 'RAW': cline += '_str(%s)' % value
                    elif token == 'CMD': cline += '_escape(%s)' % value
                    cline +=  ', '
                cline = cline[:-2] + '\\\n'
            cline = cline[:-2]
            if cline[:-1].endswith('\\\\\\\\\\n'):
                cline = cline[:-7] + cline[-1] 
            cline = '_printlist([' + cline + '])'
            del ptrbuffer[:] 
            code(cline)

        def code(stmt):
            for line in stmt.splitlines():
                codebuffer.append('  ' * len(stack) + line.strip())

        for line in template.splitlines(True):
            lineno += 1
            line = line if isinstance(line, unicode)\
                        else unicode(line, encoding=self.encoding)
            if lineno <= 2:
                m = re.search(r"%.*coding[:=]\s*([-\w\.]+)", line)
                if m: self.encoding = m.group(1)
                if m: line = line.replace('coding','coding (removed)')
            if line.strip()[:2].count('%') == 1:
                line = line.split('%',1)[1].lstrip()
                cline = split_comment(line)[0].strip()
                cmd = re.split(r'[^a-zA-Z0-9_]', cline)[0]
                flush() 
                if cmd in self.blocks or multiline:
                    cmd = multiline or cmd
                    dedent = cmd in self.dedent_blocks 
                    if dedent and not oneline and not multiline:
                        cmd = stack.pop()
                    code(line)
                    oneline = not cline.endswith(':') 
                    multiline = cmd if cline.endswith('\\') else False
                    if not oneline and not multiline:
                        stack.append(cmd)
                elif cmd == 'end' and stack:
                    code('#end(%s) %s' % (stack.pop(), line.strip()[3:]))
                elif cmd == 'include':
                    p = cline.split(None, 2)[1:]
                    if len(p) == 2:
                        code("_=_include(%s, _stdout, %s)" % (repr(p[0]), p[1]))
                    elif p:
                        code("_=_include(%s, _stdout)" % repr(p[0]))
                    else: 
                        code("_printlist(_base)")
                elif cmd == 'rebase':
                    p = cline.split(None, 2)[1:]
                    if len(p) == 2:
                        code("globals()['_rebase']=(%s, dict(%s))" % (repr(p[0]), p[1]))
                    elif p:
                        code("globals()['_rebase']=(%s, {})" % repr(p[0]))
                else:
                    code(line)
            else: 
                if line.strip().startswith('%%'):
                    line = line.replace('%%', '%', 1)
                ptrbuffer.append(yield_tokens(line))
        flush()
        return '\n'.join(codebuffer) + '\n'

    def subtemplate(self, _name, _stdout, **args):
        if _name not in self.cache:
            self.cache[_name] = self.__class__(name=_name, lookup=self.lookup)
        return self.cache[_name].execute(_stdout, **args)

    def execute(self, _stdout, **args):
        #_stdout change the html code
        env = self.defaults.copy()
        env.update({'_stdout': _stdout, '_printlist': _stdout.extend,
               '_include': self.subtemplate, '_str': self._str,
               '_escape': self._escape})
        env.update(args)
        eval(self.co, env)
        if '_rebase' in env:
            subtpl, rargs = env['_rebase']
            subtpl = self.__class__(name=subtpl, lookup=self.lookup)
            rargs['_base'] = _stdout[:] 
            del _stdout[:] 
            return subtpl.execute(_stdout, **rargs)
        return env

    def render(self, **args):
        stdout = []
        try:
            #execute error 
            self.execute(stdout, **args)
        except Exception,e:
            print e
        finally:
            return ''.join(stdout)


def template(tpl, template_adapter=SimpleTemplate, **kwargs):
    if tpl not in TEMPLATES or DEBUG:
        settings = kwargs.get('template_settings',{})
        lookup = kwargs.get('template_lookup', TEMPLATE_PATH)
        if isinstance(tpl, template_adapter):
            TEMPLATES[tpl] = tpl
            if settings: TEMPLATES[tpl].prepare(**settings)
        elif "\n" in tpl or "{" in tpl or "%" in tpl or '$' in tpl:
            TEMPLATES[tpl] = template_adapter(source=tpl, lookup=lookup, **settings)
        else:
            TEMPLATES[tpl] = template_adapter(name=tpl, lookup=lookup, **settings)
    if not TEMPLATES[tpl]:
        abort(500, 'Template (%s) not found' % tpl)
    return TEMPLATES[tpl].render(**kwargs)
