import inspect
import re

ident = re.compile(r'\w+')
ws = re.compile(r'\s*')


class NamedType(object):
    def __init__(self, name):
        self.name = name


class ListType(object):
    def __init__(self, t):
        self.t = t


class AnyType(object):
    def __init__(self):
        pass


class FieldDecl(object):
    def __init__(self, name, t, attrs):
        self.name = name
        self.t = t
        self.attrs = attrs


class SchemaParser(object):
    def __init__(self):
        pass

    def error(self, msg):
        raise Exception('%s @ %d: %r' % (msg, self.pos, self.schema))

    def check_exact(self, c):
        return self.pos + len(c) <= len(self.schema) and self.schema[self.pos:self.pos+len(c)] == c

    def consume_exact(self, c):
        self.pos += len(c)

    def require_exact(self, c):
        if self.check_exact(c):
            self.consume_exact(c)
        else:
            self.error('Missing %r' % c)

    def s(self):
        self.pos = ws.match(self.schema, self.pos).end()

    def ident(self):
        m = ident.match(self.schema, self.pos)
        if m:
            assert m.end() != self.pos
            self.pos = m.end()
            return m.group()
        else:
            return None

    def type_ref(self):
        name = self.ident()
        if name is not None:
            return NamedType(name)
        elif self.check_exact('[]'):
            self.consume_exact('[]')
            t = self.type_ref()
            if t is None:
                self.error('Missing type ref')
            return ListType(t)
        elif self.check_exact('*'):
            self.consume_exact('*')
            return AnyType()
        return None

    def attrs(self):
        attrs = []
        if not self.check_exact('@'):
            return attrs
        self.consume_exact('@')
        self.s()
        self.require_exact('[')
        self.s()
        name = self.ident()
        if name is not None:
            attrs.append(name)
            while True:
                self.s()
                if not self.check_exact(','):
                    break
                self.consume_exact(',')
                self.s()
                name = self.ident()
                if name is None:
                    self.error('Missing attr')
                attrs.append(name)
        self.s()
        self.require_exact(']')
        return attrs

    def parse_field(self):
        name = self.ident()
        if not name:
            return None
        self.s()
        self.require_exact(':')
        self.s()
        t = self.type_ref()
        if not t:
            self.error('Missing type')
        self.s()
        attrs = self.attrs()
        return FieldDecl(name, t, attrs)

    def parse(self, schema):
        self.schema = schema
        self.pos = 0

        fields = []
        while True:
            self.s()
            f = self.parse_field()
            if f is None:
                break
            fields.append(f)
        self.s()
        if self.pos != len(self.schema):
            self.error('Unexpected %r' % self.schema[self.pos])
        return fields


python_types = {
    'string': 'basestring',
    'rune': 'basestring',
}


def zero_value(t):
    if isinstance(t, NamedType):
        if t.name == 'string':
            return ''
        elif t.name == 'rune':
            return '\0'
        elif t.name == 'bool':
            return False
        elif t.name == 'int':
            return 0
        else:
            return None
    elif isinstance(t, ListType):
        return []
    else:
        assert False, t


def gen_validation(fn, ft, indent):
    src = ''
    if isinstance(ft, ListType):
        src += indent + 'assert isinstance(%s, list), (type(self), type(%s))\n' % (fn, fn)
        child_src = gen_validation('_' + fn, ft.t, indent + '  ')
        if child_src:
            src += indent + 'for _%s in %s:\n' % (fn, fn)
            src += child_src
    elif isinstance(ft, NamedType):
        ft = python_types.get(ft.name, ft.name)
        src += indent + 'assert isinstance(%s, %s), (type(self), type(%s))\n' % (fn, ft, fn)
    return src


class TreeMeta(type):
    def __new__(cls, name, parents, dct):
        assert '__schema__' in dct, dct

        # Grab the globals used while defining the class.
        cls_globals = inspect.stack()[1][0].f_globals

        p = SchemaParser()
        fields = p.parse(dct['__schema__'])

        dct['__slots__'] = [f.name for f in fields]

        src = ''
        if '__init__' not in dct:
            args = ['self'] + [f.name for f in fields if 'no_init' not in f.attrs]
            src += '\n'
            src += 'def __init__(%s):\n' % ', '.join(args)
            if fields:
                for f in fields:
                    if 'no_init' not in f.attrs:
                        src += gen_validation(f.name, f.t, '  ')
                for f in fields:
                    if 'no_init' not in f.attrs:
                        value = f.name
                    else:
                        value = repr(zero_value(f.t))
                    src += '  self.%s = %s\n' % (f.name, value)
            else:
                src += '  pass\n'

        if '__repr__' not in dct:
            args = ['type(self).__name__']
            pat = []
            for f in fields:
                if 'no_init' in f.attrs:
                    continue
                elif 'backedge' in f.attrs:
                    pat.append('...')
                else:
                    args.append('self.' + f.name)
                    pat.append('%r')
            src += '\n'
            src += 'def __repr__(self):\n'
            src += '  return "%%s(%s)" %% (%s,)' % (', '.join(pat), ', '.join(args))

        if src:
            # Inject the code into the class.
            exec src in cls_globals, dct

        return super(TreeMeta, cls).__new__(cls, name, parents, dct)


@classmethod
def visit(cls, *args):
    f = cls.__dispatchers__.get(type(args[0]))
    if f:
        return f(cls, *args)
    else:
        raise Exception("%r cannot visit %r" % (cls, type(args[0])))


def dispatch(*types):
    def annotate(f):
        f.__dispatch__ = types
        return f
    return annotate


class TypeDispatcher(type):
    def __new__(cls, name, parents, dct):
        d = {}
        for f in dct.itervalues():
            if not hasattr(f, '__dispatch__'):
                continue
            for t in f.__dispatch__:
                d[t] = f
        dct['__dispatchers__'] = d
        dct['visit'] = visit

        return super(TypeDispatcher, cls).__new__(cls, name, parents, dct)
