from ritual.base import TypeDispatcher, dispatch
import ritual.base.io
from . import model


class Generator(object):
    def __init__(self, out):
        self.out = out
        self.names = {}
        self.tmp_id = 0
        self.label_id = 0


    def alloc_temp(self):
        tmp = f'tmp_{self.tmp_id}'
        self.tmp_id += 1
        return tmp

    def alloc_label(self):
        tmp = f'label_{self.label_id}'
        self.label_id += 1
        return tmp

    def get_name(self, obj):
        name = self.names.get(obj)
        if name is not None:
            return name

        module_name = obj.module.name.replace('.', '_')
        if isinstance(obj, model.Function) or isinstance(obj, model.ExternFunction):
            prefix = 'fn'
        elif isinstance(obj, model.Struct):
            prefix = 's'
        else:
            assert False, obj
        name = f'{prefix}_{module_name}_{obj.name}'
        self.names[obj] = name
        return name


INTRINSIC_MAP = {}
INTRINSIC_MAP['bool'] = 'bool'
INTRINSIC_MAP['string'] = 'std::string'


class GenerateTypeRef(object, metaclass=TypeDispatcher):

    @dispatch(model.IntegerType)
    def visitIntegerType(cls, node, gen):
        return f'{"u" if node.unsigned else ""}int{node.width}_t'

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
            return f'std::shared_ptr<{name}>'
        else:
            return name

    @dispatch(model.TupleType)
    def visitTupleType(cls, node, gen):
        if not node.children:
            return 'void'
        children = [cls.visit(child, gen) for child in node.children]
        return f'std::tuple<{", ".join(children)}>'


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


class GenerateDeclarations(object, metaclass=TypeDispatcher):

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


class GenerateTarget(object, metaclass=TypeDispatcher):

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
            cls.visit(tgt, f'std::get<{i}>({value})', gen)

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
            cls.visit(tgt, f'{value}{deref}{f.name}', gen)


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
    oc = ord(c)
    if c in escapes:
        return escapes[c]
    elif is_printable_ascii(c):
        return c
    elif oc < 256:
        return f'\\x{oc:02x}'
    elif oc < 65536:
        return f'\\u{oc:04x}'
    else:
        return f'\\U{oc:08x}'


def is_printable_ascii(c):
    return 32 <= ord(c) < 127


def string_literal(s):
    return f'u8"{"".join([escape_char(c) for c in s])}"'


def implemented_as_ptr(t):
    return isinstance(t, model.Struct) and t.is_ref


class GenerateExpr(object, metaclass=TypeDispatcher):

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
        arg_list = ', '.join(args)
        if node.t.is_ref:
            return f'std::make_shared<{t_name}>({arg_list})', 2, True, True
        else:
            return f'{t_name}{{{arg_list}}}', 2, True, False

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node, used, gen):
        args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
        func_name = gen.get_name(node.f)
        arg_list = ', '.join(args)
        return f'{func_name}({arg_list})', 2, True, implemented_as_ptr(node.f.t.rt)

    @dispatch(model.DirectMethodCall)
    def visitDirectMethodCall(cls, node, used, gen):
        expr, is_ptr = gen_arg(node.expr, 2, gen)
        args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
        name = node.f.name
        deref = '->' if is_ptr else '.'
        arg_list = ', '.join(args)
        return f'{expr}{deref}{name}({arg_list})', 2, True, implemented_as_ptr(node.f.t.rt)

    @dispatch(model.TupleLiteral)
    def visitTupleLiteral(cls, node, used, gen):
        if used:
            args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
            arg_list = ', '.join(args)
            return f'std::make_tuple({arg_list})', 2, False, False
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
        return f'{expr}{deref}{node.field.name}', prec, False, implemented_as_ptr(node.field.t)

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
            expr = f'({t})(({tmp}){left} {node.op} ({tmp}){right})'
            prec = 3
        else:
            expr = f'{left} {node.op} {right}'
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
            gen.out.write(f'if (!({cond})) break;\n')
            gen_void(node.body, gen)
        gen.out.write('}\n')
        return None, 0, True, False


def is_nop(node):
    return isinstance(node, model.Sequence) and not node.children


def gen_arg(node, containing_prec, gen, always_capture=False):
    expr, prec, impure, is_ptr = GenerateExpr.visit(node, True, gen)
    if impure or always_capture:
        # Declare the tmp var.
        t = GenerateTypeRef.visit(node.t, gen)
        tmp = gen.alloc_temp()
        gen.out.write(f'{t} {tmp} = {expr};\n')
        return tmp, is_ptr
    else:
        if containing_prec < prec:
            expr = f'({expr})'
        return expr, is_ptr


def gen_if(node, target, gen):
    cond, _, _, _ = GenerateExpr.visit(node.cond, True, gen)
    gen.out.write(f'if ({cond}) {{\n')
    with gen.out.block():
        gen_capture(node.tbody, target, gen)
    if not is_nop(node.fbody):
        gen.out.write('} else {\n')
        with gen.out.block():
            gen_capture(node.fbody, target, gen)
    gen.out.write('}\n')


def gen_matcher(node, expr, next, gen):
    assert isinstance(node, model.StructMatch), node

    t = GenerateTypeRef.visit(node.t, gen)
    tmp = gen.alloc_temp()
    t_name = gen.get_name(node.t)
    gen.out.write(f'{t} {tmp} = std::dynamic_pointer_cast<{t_name}>({expr});\n')
    gen.out.write(f'if ({tmp} == nullptr) goto {next};\n')


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
            gen.out.write(f'{next}:\n')
        next = gen.alloc_label()

        gen.out.write('{\n')
        with gen.out.block():
            gen_matcher(case.matcher, cond, next, gen)
            gen_capture(case.expr, target, gen)
            # Jump to the exit.
            gen.out.write(f'goto {done};\n')

        gen.out.write('}\n')

    # TODO better validation.
    gen.out.write(f'{next}:\n')
    gen.out.write('abort();\n')

    # Exit
    gen.out.write(f'{done}:\n')


def gen_capture(node, target, gen):
    if target:
        if isinstance(node, model.If):
            gen_if(node, target, gen)
        else:
            expr, _, _, _ = GenerateExpr.visit(node, True, gen)
            gen.out.write(f'{target} = {expr};\n')
    else:
        gen_void(node, gen)


def gen_void(node, gen):
    expr, _, impure, _ = GenerateExpr.visit(node, False, gen)
    if expr and impure:
        gen.out.write(f'{expr};\n')


class GenerateSource(object, metaclass=TypeDispatcher):

    @classmethod
    def declare_locals(self, lcls, skip, gen):
        for lcl in lcls:
            if lcl in skip:
                continue
            gen.out.write(GenerateTypeRef.visit(lcl.t, gen)).write(f' {lcl.name};\n')

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
        gen.out.write(f' {name}(')
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
                expr = gen_arg(node.body, 16, gen)[0]
                gen.out.write(f'return {expr};\n')
        gen.out.write('}\n')

    @dispatch(model.Field)
    def visitField(cls, node, gen):
        gen.out.write(GenerateTypeRef.visit(node.t, gen)).write(f' {node.name};\n')

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
                gen.out.write(f'{f.name}({f.name})')
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
                gen.out.write(f'{f.name}({zero})')
                dirty = True

            gen.out.write(' {}\n\n')

            # Tracing destructor.
            #gen.out.write(f'~{name}() {{ std::cout << "    destroy {name}" << std::endl; }}\n')

            for f in node.fields:
                cls.visit(f, gen)
            for m in node.methods:
                cls.visit(m, gen)
        gen.out.write('};\n')

    @dispatch(model.Test)
    def visitTest(cls, node, module, index, gen):
        module_name = module.name.replace('.', '_')
        name = f'test_{module_name}_{index}'

        gen.tmp_id = 0
        gen.out.write('\n')
        gen.out.write(f'static void {name}() {{\n')
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
            gen.out.write(f'#include <{name}>\n')

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
                gen.out.write(f'std::cout << "test " << {string_literal(m.name)} << ": " << {string_literal(t.desc)} << "..." << std::endl;\n')
                gen.out.write(f'{name}();\n')
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