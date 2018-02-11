import inspect
import re

ident = re.compile(r'\w+')
dotted_name = re.compile(r'\w+(?:\.\w+)*')
ws = re.compile(r'\s*')


class NamedType(object):
    def __init__(self, name):
        self.name = name


class ListType(object):
    def __init__(self, t):
        self.t = t


class NullableType(object):
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

    def dotted_name(self):
        m = dotted_name.match(self.schema, self.pos)
        if m:
            assert m.end() != self.pos
            self.pos = m.end()
            return m.group()
        else:
            return None

    def type_ref(self):
        name = self.dotted_name()
        if name is not None:
            return NamedType(name)
        elif self.check_exact('[]'):
            self.consume_exact('[]')
            t = self.type_ref()
            if t is None:
                self.error('Missing type ref')
            return ListType(t)
        elif self.check_exact('?'):
            self.consume_exact('?')
            t = self.type_ref()
            if t is None:
                self.error('Missing type ref')
            return NullableType(t)
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


def zero_value(f):
    t = f.t
    if isinstance(t, NamedType):
        if t.name == 'string':
            return repr('')
        elif t.name == 'rune':
            return repr('\0')
        elif t.name == 'bool':
            return repr(False)
        elif t.name == 'int':
            return repr(0)
        else:
            return repr(None)
    elif isinstance(t, ListType):
        return []
    elif isinstance(t, NullableType):
        return repr(None)
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
        #src += indent + 'print %r, %s\n' % (ft, ft)
        src += indent + 'assert isinstance(%s, %s), (type(self), type(%s))\n' % (fn, ft, fn)
    elif isinstance(ft, NullableType):
        src += indent + 'if %s is not None:\n' % (fn,)
        child_indent = indent + '  '
        child_src = gen_validation(fn, ft.t, child_indent)
        if not child_src:
            child_src = child_indent + 'pass'
        src += child_src
    elif isinstance(ft, AnyType):
        pass
    else:
        assert False, ft
    return src


def init_with_arg(f):
    return 'no_init' not in f.attrs and 'simple_init' not in f.attrs


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
            args = ['self'] + [f.name for f in fields if init_with_arg(f)]
            src += '\n'
            src += 'def __init__(%s):\n' % ', '.join(args)
            if fields:
                for f in fields:
                    if init_with_arg(f):
                        src += gen_validation(f.name, f.t, '  ')
                for f in fields:
                    if init_with_arg(f):
                        value = f.name
                    elif 'no_init' in f.attrs:
                        value = zero_value(f)
                    elif 'simple_init' in f.attrs:
                        value = f.t.name + '()'
                    else:
                        assert False, f.attrs
                    src += '  self.%s = %s\n' % (f.name, value)
            else:
                src += '  pass\n'

        if '__eq__' not in dct:
            src += '\ndef __eq__(self, other):\n'
            parts = ['type(self) is type(other)']
            for f in fields:
                if 'no_compare' not in f.attrs:
                    parts.append('self.%s == other.%s' % (f.name, f.name))
            src += '  return self is other or %s\n' % ' and '.join(parts)


        if '__repr__' not in dct:
            args = ['type(self).__name__']
            pat = []
            for f in fields:
                if not init_with_arg(f):
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
            # Inject the code into the class
            pkg = cls_globals['__name__']
            qual = pkg + '.' if pkg else ''
            code = compile(src, 'TreeMeta<%s%s>' % (qual, name), 'exec')
            exec code in cls_globals, dct

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
    def __new__(cls, cls_name, parents, dct):
        d = {}
        remove = []
        for name, f in dct.iteritems():
            if not hasattr(f, '__dispatch__'):
                continue
            for t in f.__dispatch__:
                if t in d:
                    raise Exception('Multiple dispatchers for %r in %s'% (t, cls_name))
                d[t] = f
            remove.append(name)
        for name in remove:
            del dct[name]
        dct['__dispatchers__'] = d
        dct['visit'] = visit

        return super(TypeDispatcher, cls).__new__(cls, cls_name, parents, dct)
