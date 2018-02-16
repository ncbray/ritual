from base import TypeDispatcher, dispatch
import base.io
import model


class Generator(object):
    def __init__(self, out):
        self.out = out
        self.names = {}
        self.tmp_id = 0
    
    def get_name(self, obj):
        name = self.names.get(obj)
        if name is not None:
            return name

        if isinstance(obj, model.Function) or isinstance(obj, model.ExternFunction):
            name = 'fn_' + obj.name
        else:
            assert False, obj

        self.names[obj] = name
        return name


INTRINSIC_MAP = {}
INTRINSIC_MAP['bool'] = 'bool'
for sz in [8, 16, 32]:
    INTRINSIC_MAP['i%d' % sz] = 'int%d_t' % sz
INTRINSIC_MAP['string'] = 'std::string'


class GenerateTypeRef(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.IntrinsicType)
    def visitIntrinsicType(cls, node, gen):
        gen.out.write(INTRINSIC_MAP[node.name])

    @dispatch(model.TupleType)
    def visitTupleType(cls, node, gen):
        if not node.children:
            gen.out.write('void')
            return
        gen.out.write('std::tuple<')
        cls.visit(node.children[0], gen)
        for child in node.children[1:]:
            gen.out.write(', ')
            cls.visit(child, gen)
        gen.out.write('>')


def gen_param(p, gen):
    GenerateTypeRef.visit(p.t, gen)
    gen.out.write(' ').write(p.name)


def gen_params(params, gen):
    if not params:
        gen.out.write('void')
        return
    gen_param(params[0], gen)
    for p in params[1:]:
        gen.out.write(', ')
        gen_param(p, gen)


class GenerateDeclarations(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.Function, model.ExternFunction)
    def visitFunction(cls, node, gen):
        GenerateTypeRef.visit(node.t.rt, gen)
        gen.out.write(' ').write(gen.get_name(node)).write('(')
        gen_params(node.params, gen)
        gen.out.write(');\n')


class GenerateTarget(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.SetLocal)
    def visitSetLocal(cls, node, gen):
        return node.lcl.name

    @dispatch(model.DestructureTuple)
    def visitDestructureTuple(cls, node, gen):
        tgts = [cls.visit(tgt, gen) for tgt in node.args]
        return 'std::tie(%s)' % ', '.join(tgts)


escapes = {
    '\\': '\\\\',
    '"': '\\"',
    '\'': '\\\'',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
    '\f': '\\f',
    '\a': '\\a',
    '\v': '\\v',
    '?': '\\?', # Because trigraphs.
}


def escape_char(c):
    if c in escapes:
        return escapes[c]
    elif is_printable_ascii(c):
        return c
    elif ord(c) < 256:
        return '\\x%02x' % ord(c)
    elif ord(c) < 65536:
        return '\\u%04x' % ord(c)
    else:
        return '\\U%08x' % ord(c)


def is_printable_ascii(c):
    return 32 <= ord(c) < 127


class GenerateExpr(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, used, gen):
        return repr(node.value), False

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, used, gen):
        chars = [escape_char(c) for c in node.value]

        return 'u8"' + ''.join(chars) + '"', False

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node, used, gen):
        args = [gen_arg(arg, gen) for arg in node.args]
        func_name = gen.get_name(node.f)
        return '%s(%s)' % (func_name, ', '.join(args)), True

    @dispatch(model.TupleLiteral)
    def visitTupleLiteral(cls, node, used, gen):
        if used:
            args = [gen_arg(arg, gen) for arg in node.args]
            return 'std::make_tuple(' + ', '.join(args) + ')', False
        else:
            for arg in node.args:
                gen_void(arg, gen)
            return None, False

    @dispatch(model.GetLocal)
    def visitGetLocal(cls, node, used, gen):
        return node.lcl.name, False

    @dispatch(model.Sequence)
    def visitSeqeunce(cls, node, used, gen):
        for child in node.children[:-1]:
            gen_void(child, gen)
        return cls.visit(node.children[-1], used, gen)

    @dispatch(model.Assign)
    def visitAssign(cls, node, used, gen):
        assert not used
        target = GenerateTarget.visit(node.target, gen)
        value, impure = cls.visit(node.value, True, gen)
        gen.out.write(target + ' = ' + value + ';\n')
        return None, True

    @dispatch(model.BinaryOp)
    def visitBinaryOp(cls, node, used, gen):
        left = gen_arg(node.left, gen)
        right = gen_arg(node.right, gen)
        return '%s %s %s' % (left, node.op, right), True

    @dispatch(model.While)
    def visitWhile(cls, node, used, gen):
        assert not used
        gen.out.write('while (true) {\n')
        with gen.out.block():
            cond, _ = cls.visit(node.cond, True, gen)
            gen.out.write('if (!(%s)) break;\n' % cond)
            gen_void(node.body, gen)
        gen.out.write('}\n')
        return None, True


def gen_arg(node, gen):
    expr, impure = GenerateExpr.visit(node, True, gen)
    if impure:
        tmp = 'tmp_%d' % gen.tmp_id
        gen.tmp_id += 1
        gen.out.write('auto %s = %s;\n' % (tmp, expr))
        return tmp
    else:
        return expr


def gen_void(node, gen):
    expr, impure = GenerateExpr.visit(node, False, gen)
    if expr and impure:
        gen.out.write(expr).write(';\n')


class GenerateSource(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.Function)
    def visitFunction(cls, node, gen):
        gen.tmp_id = 0
        gen.out.write('\n')
        GenerateTypeRef.visit(node.t.rt, gen)
        gen.out.write(' ').write(gen.get_name(node)).write('(')
        gen_params(node.params, gen)
        gen.out.write(') {\n')
        with gen.out.block():
            # Declare locals
            params = set([p.lcl for p in node.params])
            for lcl in node.locals:
                if lcl in params:
                    continue
                GenerateTypeRef.visit(lcl.t, gen)
                gen.out.write(' ').write(lcl.name).write(';\n')

            # Generate body
            rt = node.t.rt
            is_void = isinstance(rt, model.TupleType) and len(rt.children) == 0
            if is_void:
                gen_void(node.body, gen)
            else:
                gen.out.write('return ' + gen_arg(node.body, gen)).write(';\n')
        gen.out.write('}\n')

    @dispatch(model.ExternFunction)
    def visitExternFunction(cls, node, gen):
        pass

    @dispatch(model.Program)
    def visitProgram(cls, node, gen):
        includes = ['cstdint', 'tuple', 'string']
        includes.sort()
        for name in includes:
            gen.out.write('#include <%s>\n' % name)

        gen.out.write('\n')
        for m in node.modules:
            for f in m.functions:
                GenerateDeclarations.visit(f, gen)

        for m in node.modules:
            for f in m.functions:
                cls.visit(f, gen)


def generate_source(p, out):
    gen = Generator(base.io.TabbedWriter(out))
    GenerateSource.visit(p, gen)