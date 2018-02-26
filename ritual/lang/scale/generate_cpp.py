from ritual.base import TypeDispatcher, dispatch
import ritual.base.io
import model


class Generator(object):
    def __init__(self, out):
        self.out = out
        self.names = {}
        self.tmp_id = 0

    def alloc_temp(self):
        tmp = 'tmp_%d' % self.tmp_id
        self.tmp_id += 1
        return tmp

    def get_name(self, obj):
        name = self.names.get(obj)
        if name is not None:
            return name

        if isinstance(obj, model.Function) or isinstance(obj, model.ExternFunction):
            name = 'fn_%s_%s' % (obj.module.name.replace('.', '_'), obj.name)
        elif isinstance(obj, model.Struct):
            name = 's_%s_%s' % (obj.module.name.replace('.', '_'), obj.name)
        else:
            assert False, obj

        self.names[obj] = name
        return name


INTRINSIC_MAP = {}
INTRINSIC_MAP['bool'] = 'bool'
INTRINSIC_MAP['string'] = 'std::string'


class GenerateTypeRef(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.IntegerType)
    def visitIntegerType(cls, node, gen):
        if node.unsigned:
            return 'uint%d_t' % node.width
        else:
            return 'int%d_t' % node.width

    @dispatch(model.FloatType)
    def visitFloatType(cls, node, gen):
        if node.width == 32:
            return 'float'
        elif node.width == 64:
            return 'double'
        else:
            assert False, node

    @dispatch(model.IntrinsicType)
    def visitIntrinsicType(cls, node, gen):
        return INTRINSIC_MAP[node.name]

    @dispatch(model.Struct)
    def visitStruct(cls, node, gen):
        name = gen.get_name(node)
        if node.is_ref:
            return 'std::shared_ptr<%s>' % name
        else:
            return name

    @dispatch(model.TupleType)
    def visitTupleType(cls, node, gen):
        if not node.children:
            return 'void'
        children = [cls.visit(child, gen) for child in node.children]
        return 'std::tuple<%s>' % ', '.join(children)


def gen_param(p, gen):
    gen.out.write(GenerateTypeRef.visit(p.t, gen)).write(' ').write(p.name)


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

    @dispatch(model.Struct)
    def visitStruct(cls, node, gen):
        gen.out.write('struct ').write(gen.get_name(node)).write(';\n')

    @dispatch(model.Function, model.ExternFunction)
    def visitFunction(cls, node, gen):
        if not isinstance(node, model.ExternFunction):
            gen.out.write('static ')
        gen.out.write(GenerateTypeRef.visit(node.t.rt, gen)).write(' ').write(gen.get_name(node)).write('(')
        gen_params(node.params, gen)
        gen.out.write(');\n')


class GenerateTarget(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.SetLocal)
    def visitSetLocal(cls, node, gen):
        return node.lcl.name

    @dispatch(model.SetField)
    def visitSetField(cls, node, gen):
        expr = gen_arg(node.expr, gen)
        return expr + field_deref(node.field, gen)

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


def string_literal(s):
    chars = [escape_char(c) for c in s]
    return 'u8"' + ''.join(chars) + '"'


def field_deref(f, gen):
    if f.owner.is_ref:
        sep = '->'
    else:
        sep = '.'
    return sep + f.name


class GenerateExpr(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.BooleanLiteral)
    def visitBooleanLiteral(cls, node, used, gen):
        return 'true' if node.value else 'false', False

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, used, gen):
        return repr(node.value), False

    @dispatch(model.FloatLiteral)
    def visitFloatLiteral(cls, node, used, gen):
        return node.text, False

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, used, gen):
        return string_literal(node.value), False

    @dispatch(model.Constructor)
    def visitConstructor(cls, node, used, gen):
        args = [gen_arg(arg, gen) for arg in node.args]
        t_name = gen.get_name(node.t)
        if node.t.is_ref:
            return 'std::make_shared<%s>(%s)' % (t_name, ', '.join(args)), True
        else:
            return '%s{%s}' % (t_name, ', '.join(args)), True

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

    @dispatch(model.GetField)
    def visitGetField(cls, node, used, gen):
        expr = gen_arg(node.expr, gen)
        return expr + field_deref(node.field, gen), False

    @dispatch(model.Sequence)
    def visitSeqeunce(cls, node, used, gen):
        if not node.children:
            assert not used
            return None, True
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

    @dispatch(model.PrefixOp)
    def visitPrefixOp(cls, node, used, gen):
        expr = gen_arg(node.expr, gen)
        return node.op + expr, True

    @dispatch(model.BinaryOp)
    def visitBinaryOp(cls, node, used, gen):
        left = gen_arg(node.left, gen)
        right = gen_arg(node.right, gen)
        # Small ints are automatically upcasted to "int", make sure they stay the same size and signedness.
        if isinstance(node.t, model.IntegerType) and node.t.width < 32 and node.op not in ['==', '!=', '<', '<=', '>', '>=']:
            t = GenerateTypeRef.visit(node.t, gen)
            tmp = 'unsigned int' if node.t.unsigned else 'int'
            expr = '(%s)((%s)%s %s (%s)%s)' % (t, tmp, left, node.op, tmp, right)
        else:
            expr = '%s %s %s' % (left, node.op, right)
        return expr, True

    @dispatch(model.If)
    def visitIf(cls, node, used, gen):
        tmp = None
        if used:
            tmp = gen.alloc_temp()
            gen.out.write(GenerateTypeRef.visit(node.rt, gen)).write(' ').write(tmp).write(';\n')

        cond, _ = cls.visit(node.cond, True, gen)
        gen.out.write('if (%s) {\n' % cond)
        with gen.out.block():
            gen_capture(node.t, tmp, gen)
        gen.out.write('} else {\n')
        with gen.out.block():
            gen_capture(node.f, tmp, gen)
        gen.out.write('}\n')
        return tmp, True

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
        tmp = gen.alloc_temp()
        gen.out.write('auto %s = %s;\n' % (tmp, expr))
        return tmp
    else:
        return expr


def gen_capture(node, target, gen):
    if target:
        expr, _ = GenerateExpr.visit(node, True, gen)
        gen.out.write('%s = %s;\n' % (target, expr))
    else:
        gen_void(node, gen)

def gen_void(node, gen):
    expr, impure = GenerateExpr.visit(node, False, gen)
    if expr and impure:
        gen.out.write(expr).write(';\n')


class GenerateSource(object):
    __metaclass__ = TypeDispatcher

    @classmethod
    def declare_locals(self, lcls, skip, gen):
        for lcl in lcls:
            if lcl in skip:
                continue
            gen.out.write(GenerateTypeRef.visit(lcl.t, gen)).write(' ').write(lcl.name).write(';\n')

    @dispatch(model.Function)
    def visitFunction(cls, node, gen):
        gen.tmp_id = 0
        gen.out.write('\n')
        gen.out.write('static ').write(GenerateTypeRef.visit(node.t.rt, gen))
        gen.out.write(' ').write(gen.get_name(node)).write('(')
        gen_params(node.params, gen)
        gen.out.write(') {\n')
        with gen.out.block():
            # Declare locals
            params = set([p.lcl for p in node.params])
            cls.declare_locals(node.locals, params, gen)

            # Generate body
            rt = node.t.rt
            is_void = isinstance(rt, model.TupleType) and len(rt.children) == 0
            if is_void:
                gen_void(node.body, gen)
            else:
                gen.out.write('return ' + gen_arg(node.body, gen)).write(';\n')
        gen.out.write('}\n')

    @dispatch(model.Field)
    def visitField(cls, node, gen):
        gen.out.write(GenerateTypeRef.visit(node.t, gen)).write(' ').write(node.name).write(';\n')

    @dispatch(model.Struct)
    def visitStruct(cls, node, gen):
        name = gen.get_name(node)
        gen.out.write('\n')
        gen.out.write('struct ').write(name).write(' {\n')
        with gen.out.block():

            if len(node.fields) == 1:
                gen.out.write('explicit ')
            gen.out.write(name).write('(')

            # Arguments
            for i, f in enumerate(node.fields):
                if i != 0:
                    gen.out.write(', ')
                gen.out.write(GenerateTypeRef.visit(f.t, gen)).write(' ').write(f.name)
            gen.out.write(') : ')

            # Initializers
            for i, f in enumerate(node.fields):
                if i != 0:
                    gen.out.write(', ')
                gen.out.write(f.name).write('(').write(f.name).write(')')

            gen.out.write(' {}\n\n')

            # Default constructor.
            # TODO zero value initialization?
            gen.out.write(name).write('()')
            dirty = False
            for f in node.fields:
                if isinstance(f.t, model.IntegerType):
                    zero = '0'
                elif isinstance(f.t, model.FloatType):
                    zero = '0'
                elif f.t.name == 'bool':
                    zero = 'false'
                else:
                    continue
                if dirty:
                    gen.out.write(', ')
                else:
                    gen.out.write(' : ')
                gen.out.write(f.name).write('(').write(zero).write(')')
                dirty = True

            gen.out.write(' {}\n\n')



            for f in node.fields:
                cls.visit(f, gen)
        gen.out.write('};\n')

    @dispatch(model.Test)
    def visitTest(cls, node, module, index, gen):
        name = 'test_%s_%d' % (module.name.replace('.', '_'), index)

        gen.tmp_id = 0
        gen.out.write('\n')
        gen.out.write('static void ').write(name).write('() {\n')
        with gen.out.block():
            cls.declare_locals(node.locals, set(), gen)
            gen_void(node.body, gen)
        gen.out.write('}\n')
        return name

    @dispatch(model.Program)
    def visitProgram(cls, node, gen):
        includes = ['cstdint', 'iostream', 'tuple', 'string']
        includes.sort()
        for name in includes:
            gen.out.write('#include <%s>\n' % name)

        structs = []
        for m in node.modules:
            structs += m.structs
        structs = sort_structs(structs)

        gen.out.write('\n')
        for s in structs:
            GenerateDeclarations.visit(s, gen)
        gen.out.write('\n')
        for m in node.modules:
            for f in m.extern_funcs:
                GenerateDeclarations.visit(f, gen)
        gen.out.write('\n')
        for m in node.modules:
            for f in m.funcs:
                GenerateDeclarations.visit(f, gen)

        for s in structs:
            cls.visit(s, gen)

        for m in node.modules:
            for f in m.funcs:
                cls.visit(f, gen)


        gen.out.write('\n')
        gen.out.write('void entrypoint(void) {\n')
        with gen.out.block():
            gen.out.write(gen.get_name(node.entrypoint)).write('();\n')
        gen.out.write('}\n')


        # Tests
        tests = []
        for m in node.modules:
            for i, t in enumerate(m.tests):
                tests.append((cls.visit(t, m, i, gen), m, t))

        gen.out.write('\n')
        gen.out.write('void run_all_tests(void) {\n')
        with gen.out.block():
            gen.out.write('std::cout << "TESTING" << std::endl;\n')
            gen.out.write('\n')
            for name, m, t in tests:
                gen.out.write('std::cout << "test " << %s << ": " << %s << "..." << std::endl;\n' % (string_literal(m.name), string_literal(t.desc)))
                gen.out.write('%s();\n' % name)
            gen.out.write('\n')
            gen.out.write('std::cout << "DONE" << std::endl;\n')
            gen.out.write('std::cout << std::endl;\n')
        gen.out.write('}\n')


# TODO something less O(n^2)-ish
def sort_structs(pending):
    out = []
    done = set()

    while pending:
        defer = []
        for s in pending:
            for f in s.fields:
                if isinstance(f.t, model.Struct) and f.t not in done:
                    defer.append(s)
                    break
            else:
                out.append(s)
                done.add(s)
        # Recursive value types?
        assert len(pending) != len(defer), pending
        pending = defer
    return out


def generate_source(p, out):
    gen = Generator(ritual.base.io.TabbedWriter(out))
    GenerateSource.visit(p, gen)