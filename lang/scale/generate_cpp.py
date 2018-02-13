from base import TypeDispatcher, dispatch
import base.io
import model


class Generator(object):
    def __init__(self, out):
        self.out = out
        self.names = {}
    
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
for sz in [8, 16, 32]:
    INTRINSIC_MAP['i%d' % sz] = 'int%d_t' % sz


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


class GenerateExpr(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, used, gen):
        return repr(node.value)

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node, used, gen):
        args = [cls.visit(arg, True, gen) for arg in node.args]
        func_name = gen.get_name(node.f)
        return '%s(%s)' % (func_name, ', '.join(args))

    @dispatch(model.TupleLiteral)
    def visitTupleLiteral(cls, node, used, gen):
        args = [cls.visit(arg, used, gen) for arg in node.args]
        if used:
            return 'std::make_tuple(' + ', '.join(args) + ')'

    @dispatch(model.GetLocal)
    def visitGetLocal(cls, node, used, gen):
        return node.lcl.name


class GenerateSource(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.Function)
    def visitFunction(cls, node, gen):
        gen.out.write('\n')
        GenerateTypeRef.visit(node.t.rt, gen)
        gen.out.write(' ').write(gen.get_name(node)).write('(')
        gen_params(node.params, gen)
        gen.out.write(') {\n')
        with gen.out.block():
            expr = GenerateExpr.visit(node.body, True, gen)
            gen.out.write('return ' + expr + ';\n')
        gen.out.write('}\n')

    @dispatch(model.ExternFunction)
    def visitExternFunction(cls, node, gen):
        pass

    @dispatch(model.Program)
    def visitProgram(cls, node, gen):
        includes = ['cstdint', 'tuple']
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