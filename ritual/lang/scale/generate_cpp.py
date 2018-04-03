from ritual.base import TypeDispatcher, dispatch
import ritual.base.io
import model


class Generator(object):
    def __init__(self, out):
        self.out = out
        self.names = {}
        self.tmp_id = 0
        self.label_id = 0


    def alloc_temp(self):
        tmp = 'tmp_%d' % self.tmp_id
        self.tmp_id += 1
        return tmp

    def alloc_label(self):
        tmp = 'label_%d' % self.label_id
        self.label_id += 1
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
    def visitSetLocal(cls, node, value, gen):
        gen.out.write(node.lcl.name + ' = ' + value + ';\n')

    @dispatch(model.SetField)
    def visitSetField(cls, node, value, gen):
        prec = 2
        expr, is_ptr = gen_arg(node.expr, 2, gen)
        deref = '->' if is_ptr else '.'
        gen.out.write(expr + deref + node.field.name + ' = ' + value + ';\n')

    @dispatch(model.DestructureTuple)
    def visitDestructureTuple(cls, node, value, gen):
        for i, tgt in enumerate(node.args):
            cls.visit(tgt, 'std::get<%d>(%s)' % (i, value), gen)

    @dispatch(model.DestructureStruct)
    def visitDestructureStruct(cls, node, value, gen):
        t = node.t
        all_fields = t.fields
        current = t.parent
        while current:
            all_fields = current.fields + all_fields
            current = current.parent

        deref = '->' if t.is_ref else '.'

        assert len(all_fields) == len(node.args)
        for i, tgt in enumerate(node.args):
            f = all_fields[i]
            cls.visit(tgt, '%s%s%s' % (value, deref, f.name), gen)


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


binop_prec = {
    '*': 5,
    '/': 5,
    '%': 5,
    '+': 6,
    '-': 6,
    '<<': 7,
    '>>': 7,
    '<': 9,
    '<=': 9,
    '>': 9,
    '>=': 9,
    '==': 10,
    '!=': 10,
    '&': 11,
    '^': 12,
    '|': 13,
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


def implemented_as_ptr(t):
    return isinstance(t, model.Struct) and t.is_ref


class GenerateExpr(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.BooleanLiteral)
    def visitBooleanLiteral(cls, node, used, gen):
        literal = 'true' if node.value else 'false'
        return literal, 0, False, False

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, used, gen):
        literal = repr(node.value)
        return literal, 0, False, False

    @dispatch(model.FloatLiteral)
    def visitFloatLiteral(cls, node, used, gen):
        literal = node.text
        if node.t.width == 32:
            literal += 'f'
        return literal, 0, False, False

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, used, gen):
        literal = string_literal(node.value)
        return literal, 0, False, False

    @dispatch(model.Constructor)
    def visitConstructor(cls, node, used, gen):
        args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
        t_name = gen.get_name(node.t)
        if node.t.is_ref:
            return 'std::make_shared<%s>(%s)' % (t_name, ', '.join(args)), 2, True, True
        else:
            return '%s{%s}' % (t_name, ', '.join(args)), 2, True, False

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node, used, gen):
        args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
        func_name = gen.get_name(node.f)
        return '%s(%s)' % (func_name, ', '.join(args)), 2, True, implemented_as_ptr(node.f.t.rt)

    @dispatch(model.DirectMethodCall)
    def visitDirectMethodCall(cls, node, used, gen):
        expr, is_ptr = gen_arg(node.expr, 2, gen)
        args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
        name = node.f.name
        deref = '->' if is_ptr else '.'
        return '%s%s%s(%s)' % (expr, deref, name, ', '.join(args)), 2, True, implemented_as_ptr(node.f.t.rt)

    @dispatch(model.TupleLiteral)
    def visitTupleLiteral(cls, node, used, gen):
        if used:
            args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
            return 'std::make_tuple(' + ', '.join(args) + ')', 2, False, False
        else:
            for arg in node.args:
                gen_void(arg, gen)
            return None, 0, False, False

    @dispatch(model.GetLocal)
    def visitGetLocal(cls, node, used, gen):
        return node.lcl.name, 0, False, implemented_as_ptr(node.lcl.t) or node.lcl.name == 'this'

    @dispatch(model.GetField)
    def visitGetField(cls, node, used, gen):
        prec = 2
        expr, is_ptr = gen_arg(node.expr, prec, gen)
        # TODO: has side effect?
        deref = '->' if is_ptr else '.'
        return expr + deref + node.field.name, prec, False, implemented_as_ptr(node.field.t)

    @dispatch(model.Sequence)
    def visitSeqeunce(cls, node, used, gen):
        if not node.children:
            assert not used
            return None, 0, True, False
        for child in node.children[:-1]:
            gen_void(child, gen)
        return cls.visit(node.children[-1], used, gen)

    @dispatch(model.Assign)
    def visitAssign(cls, node, used, gen):
        assert not used
        value, _ = gen_arg(node.value, 17, gen, always_capture=True)
        GenerateTarget.visit(node.target, value, gen)
        return None, 0, False, False

    @dispatch(model.PrefixOp)
    def visitPrefixOp(cls, node, used, gen):
        prec = 3
        expr, _ = gen_arg(node.expr, prec, gen)
        # TODO: has side effect?
        return node.op + expr, prec, False, False

    @dispatch(model.BinaryOp)
    def visitBinaryOp(cls, node, used, gen):
        prec = binop_prec[node.op]
        left, _ = gen_arg(node.left, prec, gen)
        right, _ = gen_arg(node.right, prec-1, gen)
        # Small ints are automatically upcasted to "int", make sure they stay the same size and signedness.
        if isinstance(node.t, model.IntegerType) and node.t.width < 32 and node.op not in ['==', '!=', '<', '<=', '>', '>=']:
            t = GenerateTypeRef.visit(node.t, gen)
            tmp = 'unsigned int' if node.t.unsigned else 'int'
            expr = '(%s)((%s)%s %s (%s)%s)' % (t, tmp, left, node.op, tmp, right)
            prec = 3
        else:
            expr = '%s %s %s' % (left, node.op, right)
        # TODO: has side effect?
        return expr, prec, False, False

    @dispatch(model.If)
    def visitIf(cls, node, used, gen):
        tmp = None
        if used:
            tmp = gen.alloc_temp()
            gen.out.write(GenerateTypeRef.visit(node.t, gen)).write(' ').write(tmp).write(';\n')
        gen_if(node, tmp, gen)
        return tmp, 0, False, implemented_as_ptr(node.t)

    @dispatch(model.Match)
    def visitMatch(cls, node, used, gen):
        tmp = None
        if used:
            tmp = gen.alloc_temp()
            gen.out.write(GenerateTypeRef.visit(node.rt, gen)).write(' ').write(tmp).write(';\n')
        gen_match(node, tmp, gen)
        return tmp, 0, False, implemented_as_ptr(node.rt)

    @dispatch(model.While)
    def visitWhile(cls, node, used, gen):
        assert not used
        gen.out.write('while (true) {\n')
        with gen.out.block():
            cond, _, _, _ = cls.visit(node.cond, True, gen)
            gen.out.write('if (!(%s)) break;\n' % cond)
            gen_void(node.body, gen)
        gen.out.write('}\n')
        return None, 0, True, False


def is_nop(node):
    return isinstance(node, model.Sequence) and not node.children


def gen_arg(node, containing_prec, gen, always_capture=False):
    expr, prec, impure, is_ptr = GenerateExpr.visit(node, True, gen)
    if impure or always_capture:
        tmp = gen.alloc_temp()
        gen.out.write('auto %s = %s;\n' % (tmp, expr))
        return tmp, is_ptr
    else:
        if containing_prec < prec:
            expr = '(%s)' % expr
        return expr, is_ptr


def gen_if(node, target, gen):
    cond, _, _, _ = GenerateExpr.visit(node.cond, True, gen)
    gen.out.write('if (%s) {\n' % cond)
    with gen.out.block():
        gen_capture(node.tbody, target, gen)
    if not is_nop(node.fbody):
        gen.out.write('} else {\n')
        with gen.out.block():
            gen_capture(node.fbody, target, gen)
    gen.out.write('}\n')


def gen_matcher(node, expr, next, gen):
    assert isinstance(node, model.StructMatch), node

    tmp = gen.alloc_temp()
    t_name = gen.get_name(node.t)
    gen.out.write('auto %s = std::dynamic_pointer_cast<%s>(%s);\n' % (tmp, t_name, expr))
    gen.out.write('if (%s == nullptr) goto ' % tmp).write(next).write(';\n')


def gen_match(node, target, gen):
    if not node.cases:
        assert not target, node
        gen_void(node.cond, gen)
        return

    cond, _ = gen_arg(node.cond, 17, gen, always_capture=True)
    done = gen.alloc_label()

    for i, case in enumerate(node.cases):
        first = i == 0
        last = i == len(node.cases) - 1
        if not first:
            gen.out.write(next).write(':\n')
        next = gen.alloc_label()

        gen.out.write('{\n')
        with gen.out.block():
            gen_matcher(case.matcher, cond, next, gen)
            gen_capture(case.expr, target, gen)
            # Jump to the exit.
            gen.out.write('goto ').write(done).write(';\n')

        gen.out.write('}\n')

    # TODO better validation.
    gen.out.write(next).write(':\n')
    gen.out.write('abort();\n')

    # Exit
    gen.out.write(done).write(':\n')


def gen_capture(node, target, gen):
    if target:
        if isinstance(node, model.If):
            gen_if(node, target, gen)
        else:
            expr, _, _, _ = GenerateExpr.visit(node, True, gen)
            gen.out.write('%s = %s;\n' % (target, expr))
    else:
        gen_void(node, gen)


def gen_void(node, gen):
    expr, _, impure, _ = GenerateExpr.visit(node, False, gen)
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
        is_method = node.self != None

        gen.tmp_id = 0
        gen.label_id = 0
        gen.out.write('\n')
        if is_method:
            if node.is_overridden and not node.overrides:
                gen.out.write('virtual ')
        else:
            gen.out.write('static ')
        gen.out.write(GenerateTypeRef.visit(node.t.rt, gen))

        name = node.name if is_method else gen.get_name(node)
        gen.out.write(' ').write(name).write('(')
        gen_params(node.params, gen)
        gen.out.write(') ')
        if node.overrides:
            gen.out.write('override ')
        gen.out.write('{\n')
        with gen.out.block():
            # Declare locals
            params = set([p.lcl for p in node.params])
            if is_method:
                # HACK
                node.self.name = 'this'
                params.add(node.self)
            cls.declare_locals(node.locals, params, gen)

            # Generate body
            rt = node.t.rt
            is_void = isinstance(rt, model.TupleType) and len(rt.children) == 0
            if is_void:
                gen_void(node.body, gen)
            else:
                gen.out.write('return ' + gen_arg(node.body, 16, gen)[0]).write(';\n')
        gen.out.write('}\n')

    @dispatch(model.Field)
    def visitField(cls, node, gen):
        gen.out.write(GenerateTypeRef.visit(node.t, gen)).write(' ').write(node.name).write(';\n')

    @dispatch(model.Struct)
    def visitStruct(cls, node, gen):
        name = gen.get_name(node)
        gen.out.write('\n')
        gen.out.write('struct ').write(name)
        if node.parent:
            gen.out.write(' : public ').write(gen.get_name(node.parent))
        gen.out.write(' {\n')
        with gen.out.block():

            parent_fields = []
            current = node.parent
            while current:
                parent_fields = current.fields + parent_fields
                current = current.parent
            local_fields = node.fields
            all_fields = parent_fields + local_fields

            if len(all_fields) == 1:
                gen.out.write('explicit ')
            gen.out.write(name).write('(')

            # Arguments
            for i, f in enumerate(all_fields):
                if i != 0:
                    gen.out.write(', ')
                gen.out.write(GenerateTypeRef.visit(f.t, gen)).write(' ').write(f.name)
            gen.out.write(') : ')

            # Initializers
            dirty = False
            if node.parent:
                gen.out.write(gen.get_name(node.parent)).write('(')
                gen.out.write(', '.join([f.name for f in parent_fields]))
                gen.out.write(')')
                dirty = True
            for f in local_fields:
                if dirty:
                    gen.out.write(', ')
                gen.out.write(f.name).write('(').write(f.name).write(')')
                dirty = True

            gen.out.write(' {}\n\n')

            # Default constructor.
            # TODO zero value initialization?
            gen.out.write(name).write('()')
            dirty = False
            if node.parent:
                gen.out.write(' : ').write(gen.get_name(node.parent)).write('()')
                dirty = True
            for f in local_fields:
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

            # Tracing destructor.
            #gen.out.write('~').write(name).write('() {std::cout << "    destroy %s" << std::endl;}\n' % name)

            for f in node.fields:
                cls.visit(f, gen)
            for m in node.methods:
                cls.visit(m, gen)
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
            if s.parent and s.parent not in done:
                defer.append(s)
                continue
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