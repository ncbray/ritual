import inspect

python_types = {
    'string': 'basestring',
    'rune': 'basestring',
}

def gen_validation(fn, ft, indent):
    src = ''
    if ft.startswith('[]'):
        src += indent + 'assert isinstance(%s, list), (type(self), type(%s))\n' % (fn, fn)
        child_src = gen_validation('_' + fn, ft[2:], indent + '  ')
        if child_src:
            src += indent + 'for _%s in %s:\n' % (fn, fn)
            src += child_src
    elif ft != '*':
        ft = python_types.get(ft, ft)
        src += indent + 'assert isinstance(%s, %s), (type(self), type(%s))\n' % (fn, ft, fn)
    return src

class TreeMeta(type):
    def __new__(cls, name, parents, dct):
        assert '__schema__' in dct, dct

        # Grab the globals used while defining the class.
        cls_globals = inspect.stack()[1][0].f_globals

        schema = dct['__schema__']
        fields = [f.split(':') for f in schema.split()]
        dct['__slots__'] = [f[0] for f in fields]

        src = ''
        if '__init__' not in dct:
            args = ['self'] + [f[0] for f in fields]
            src += '\n'
            src += 'def __init__(%s):\n' % ', '.join(args)
            if fields:
                for fn, ft in fields:
                    src += gen_validation(fn, ft, '  ')
                for fn, ft in fields:
                    src += '  self.%s = %s\n' % (fn, fn)
            else:
                src += '  pass\n'

        if '__repr__' not in dct:
            args = ['type(self).__name__']
            pat = []
            for fn, _ in fields:
                args.append('self.' + fn)
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
