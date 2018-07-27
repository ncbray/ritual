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
            if obj.self:
                name = f'm_{module_name}_{obj.self.t.name}_{obj.name}'
            else:
                name = f'f_{module_name}_{obj.name}'
        elif isinstance(obj, model.Struct):
            name = f's_{module_name}_{obj.name}'
        else:
            assert False, obj

        self.names[obj] = name
        return name


INTRINSIC_MAP = {}
INTRINSIC_MAP['bool'] = 'bool'
INTRINSIC_MAP['string'] = 'std::string'


class GenerateTypeRef(object, metaclass=TypeDispatcher):

    @dispatch(model.Struct)
    def visitStruct(cls, node, gen):
        tag = node.tag
        if isinstance(tag, model.UserTypeTag):
            name = gen.get_name(node)
            if node.is_ref:
                return f'std::shared_ptr<{name}>'
            else:
                return name
        elif isinstance(tag, model.IntegerTypeTag):
            return f'{"u" if tag.unsigned else ""}int{tag.width}_t'
        elif isinstance(tag, model.FloatTypeTag):
            if tag.width == 32:
                return 'float'
            elif tag.width == 64:
                return 'double'
            else:
                assert False, node
        elif isinstance(tag, model.IntrinsicTypeTag):
            return INTRINSIC_MAP[tag.name]
        else:
            assert False, node.tag

    @dispatch(model.TupleType)
    def visitTupleType(cls, node, gen):
        if not node.children:
            return 'void'
        children = [cls.visit(child, gen) for child in node.children]
        return f'std::tuple<{", ".join(children)}>'


def gen_param(p, as_ref, gen):
    gen.out.write(GenerateTypeRef.visit(p.t, gen))
    if as_ref:
        gen.out.write('&')
    gen.out.write(' ').write(p.name)


def gen_params(params, out_of_line_method, gen):
    if not params:
        gen.out.write('void')
        return
    gen_param(params[0], out_of_line_method, gen)
    for p in params[1:]:
        gen.out.write(', ')
        gen_param(p, False, gen)


class GenerateDeclarations(object, metaclass=TypeDispatcher):

    @dispatch(model.Struct)
    def visitStruct(cls, node, gen):
        gen.out.write('struct ').write(gen.get_name(node)).write(';\n')

    @dispatch(model.Function, model.ExternFunction)
    def visitFunction(cls, node, gen):
        if not isinstance(node, model.ExternFunction):
            gen.out.write('static ')
        gen.out.write(GenerateTypeRef.visit(node.t.rt, gen)).write(' ').write(gen.get_name(node)).write('(')
        if node.self:
            gen_params([node.self] + node.params, True, gen)
        else:
            gen_params(node.params, False, gen)
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
    '\0': '\\0',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
    '\f': '\\f',
    '\a': '\\a',
    '\v': '\\v',
    '?': '\\?', # Because trigraphs.
}


named_arith_ops = [
    ('add', '+', 6),
    ('sub', '-', 6),
    ('mul', '*', 5),
    ('div', '/', 5),
    ('mod', '%', 5),
]

named_bit_ops = [
    ('and', '&', 11),
    ('or', '|', 13),
    ('xor', '^', 12),
]

named_compare_ops = [
    ('eq', '==', 10),
    ('ne', '!=', 10),
    ('lt', '<', 9),
    ('le', '<=', 9),
    ('gt', '>', 9),
    ('ge', '>=', 9),
]

named_all_ops = named_arith_ops + named_bit_ops + named_compare_ops

op_name = {}
for name, op, prec in named_all_ops:
    op_name[op] = name

compare_ops = set([op[1] for op in named_compare_ops])


def is_printable_ascii(c):
    return 32 <= ord(c) < 127


# Note: don't use hex escape sequences, they interact badly with subsequent hex characters.
def escape_char(c):
    oc = ord(c)
    if c in escapes:
        return escapes[c]
    elif is_printable_ascii(c):
        return c
    elif oc < 65536:
        return f'\\u{oc:04x}'
    else:
        return f'\\U{oc:08x}'


def string_literal(s):
    return f'u8"{"".join([escape_char(c) for c in s])}"s'


def implemented_as_ptr(t):
    return isinstance(t, model.Struct) and t.is_ref


def gen_runtime_op(op, t, c_type, ret_type, gen):
    name = op_name[op]
    gen.out.write(f"""
static inline {ret_type} op_{t}_{name}({c_type} a, {c_type} b) {{
    return a {op} b;
}}
""")

def gen_runtime_casted_op(op, t, c_type, ret_type, widen, gen):
    name = op_name[op]
    gen.out.write(f"""
static inline {ret_type} op_{t}_{name}({c_type} a, {c_type} b) {{
    return ({ret_type})(({widen})a {op} ({widen})b);
}}
""")



def gen_runtime(gen):
    gen_runtime_op('+', 'string', 'std::string', 'std::string', gen)
    gen_runtime_op('==', 'string', 'std::string', 'bool', gen)
    gen_runtime_op('!=', 'string', 'std::string', 'bool', gen)

    # Integers
    for width in [8, 16, 32, 64]:
        for unsigned in [False, True]:
            t = f'{"u" if unsigned else "i"}{width}'
            c_type = f'{"u" if unsigned else ""}int{width}_t'

            for name, op, prec in named_arith_ops:
                if width < 32:
                    widen = 'unsigned int' if unsigned else 'int'
                    gen_runtime_casted_op(op, t, c_type, c_type, widen, gen)
                else:
                    gen_runtime_op(op, t, c_type, c_type, gen)

            for name, op, prec in named_bit_ops:
                gen_runtime_op(op, t, c_type, c_type, gen)

            for name, op, prec in named_compare_ops:
                gen_runtime_op(op, t, c_type, 'bool', gen)

    # Floats
    for width in [32, 64]:
        t = f'f{width}'
        c_type = 'float' if width == 32 else 'double'

        for name, op, prec in named_arith_ops:
            if op == '%':
                continue
            gen_runtime_op(op, t, c_type, c_type, gen)

        for name, op, prec in named_compare_ops:
            gen_runtime_op(op, t, c_type, 'bool', gen)

    # Boolean
    t = 'bool'
    c_type = 'bool'
    for name, op, prec in named_bit_ops:
        gen_runtime_op(op, t, c_type, c_type, gen)

    for name, op, prec in named_compare_ops:
        gen_runtime_op(op, t, c_type, 'bool', gen)


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
        if node.t.tag.width == 32:
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
        name = gen.get_name(node.f)
        return f'{name}({", ".join([expr] + args)})', 2, True, implemented_as_ptr(node.t)

    @dispatch(model.IndirectMethodCall)
    def visitIndirectMethodCall(cls, node, used, gen):
        expr, is_ptr = gen_arg(node.expr, 2, gen)
        args = [gen_arg(arg, 17, gen)[0] for arg in node.args]
        name = node.name
        deref = '->' if is_ptr else '.'
        return f'{expr}{deref}{name}({", ".join(args)})', 2, True, implemented_as_ptr(node.t)

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
        left, _ = gen_arg(node.left, 17, gen)
        right, _ = gen_arg(node.right, 17, gen)

        # TODO: lookup operators on structs.

        op_type = node.left.t.name # HACK
        expr = f'op_{op_type}_{op_name[node.op]}({left}, {right})'
        prec = 2

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
    def visitFunction(cls, node, inline_method, gen):
        gen.tmp_id = 0
        gen.label_id = 0
        gen.out.write('\n')
        if inline_method:
            if node.is_overridden and not node.overrides:
                gen.out.write('virtual ')
        else:
            gen.out.write('static ')
        gen.out.write(GenerateTypeRef.visit(node.t.rt, gen))

        declared_params = node.params
        all_params = set([p.lcl for p in node.params])
        out_of_line_method = False
        if node.self != None:
            all_params.add(node.self.lcl)
            # HACK
            if inline_method:
                self_name = 'this'
            else:
                self_name = 'self'
                declared_params = [node.self] + declared_params
                out_of_line_method = True
            node.self.name = self_name
            node.self.lcl.name = self_name


        name = node.name if inline_method else gen.get_name(node)
        gen.out.write(f' {name}(')
        gen_params(declared_params, out_of_line_method, gen)
        gen.out.write(') ')
        if inline_method and node.overrides:
            gen.out.write('override ')
        gen.out.write('{\n')

        # Body
        with gen.out.block():
            # Declare locals
            cls.declare_locals(node.locals, all_params, gen)

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
                if isinstance(f.t, model.Struct):
                    tag = f.t.tag
                    if isinstance(tag, model.IntegerTypeTag):
                        zero = '0'
                    elif isinstance(tag, model.FloatTypeTag):
                        zero = '0'
                    elif isinstance(tag, model.IntrinsicTypeTag ) and tag.name == 'bool':
                        zero = 'false'
                    else:
                        continue
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
                # TODO call out-of-line methods, trim delcared methods.
                cls.visit(m, True, gen)
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

        # Use "s" suffix to preserve internal null characters.
        gen.out.write('\nusing namespace std::string_literals;\n')

        gen_runtime(gen)

        # Collect all the structs and functions in the program.
        structs = []
        funcs = []
        externs = []
        for m in node.modules:
            structs += m.structs
            funcs += m.funcs
            externs += m.extern_funcs
            for s in m.structs:
                funcs += s.methods
        structs = sort_structs(structs)

        # Forward declarations
        gen.out.write('\n')
        for s in structs:
            GenerateDeclarations.visit(s, gen)
        gen.out.write('\n')
        for f in externs:
            GenerateDeclarations.visit(f, gen)
        gen.out.write('\n')
        for f in funcs:
            GenerateDeclarations.visit(f, gen)

        for s in structs:
            cls.visit(s, gen)

        for f in funcs:
            cls.visit(f, False, gen)

        # Tests
        tests = []
        for m in node.modules:
            for i, t in enumerate(m.tests):
                tests.append((cls.visit(t, m, i, gen), m, t))

        # Run all tests
        gen.out.write('\n')
        gen.out.write('static void run_all_tests(void) {\n')
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

        # Main
        gen.out.write('\n')
        gen.out.write('int main() {\n')
        with gen.out.block():
            gen.out.write('run_all_tests();\n')
            gen.out.write(gen.get_name(node.entrypoint)).write('();\n')
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
                if isinstance(f.t, model.Struct) and isinstance(f.t.tag, model.UserTypeTag) and f.t not in done:
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