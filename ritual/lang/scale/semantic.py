from ritual.base import TypeDispatcher, dispatch
from collections import OrderedDict
from . import model
from . import parser

POISON_EXPR = model.PoisonExpr()
POISON_TARGET = model.PoisonTarget()

POISON_TYPE = model.PoisonType()
MODULE_TYPE = model.ModuleType()
VOID_TYPE = model.TupleType([])


class NamespaceScope(object):
    __slots__ = ['semantic', 'namespace']

    def __init__(self, semantic, namespace):
        self.semantic = semantic
        self.namespace = namespace

    def __enter__(self):
        self.semantic._namespaces.insert(0, self.namespace)

    def __exit__(self, type, value, traceback):
        old = self.semantic._namespaces.pop(0)
        assert old is self.namespace, old


class SemanticPass(object):
    def __init__(self, status):
        self.status = status
        self.modules = OrderedDict()
        self.builtins = OrderedDict()
        self._namespaces = [self.builtins]

        self.tuple_cache = {}
        self.func_cache = {}

    def lookup(self, name):
        for ns in self._namespaces:
            if name in ns:
                return ns[name]
        return None

    def namespace(self, ns):
        return NamespaceScope(self, ns)

    def register(self, loc, name, obj):
        for i, ns in enumerate(self._namespaces):
            if name in ns:
                if i == 0:
                    self.status.error('tried to redefine "%s"' % name, loc)
                else:
                    self.status.error('"%s" shadows an existing name' % name, loc)
                # TODO Poison?
                return False
        self._namespaces[0][name] = obj
        return True

    def define_lcl(self, loc, name, t):
        lcl = model.Local(loc, name, t)
        self.register(loc, name, lcl)
        self.func.locals.append(lcl)
        return lcl


def make_tuple_type(children, semantic):
    if len(children) == 0:
        return VOID_TYPE
    elif len(children) == 1:
        return children[0]
    key = tuple(children)
    t = semantic.tuple_cache.get(key)
    if not t:
        t = model.TupleType(children)
        semantic.tuple_cache[key] = t
    return t


def make_function_type(params, returns, semantic):
    rt = make_tuple_type(returns, semantic)
    key = (tuple(params), rt)
    t = semantic.func_cache.get(key)
    if not t:
        t = model.FunctionType(params, rt)
        semantic.func_cache[key] = t
    return t


class IndexNamespace(object, metaclass=TypeDispatcher):

    @dispatch(parser.TestDecl)
    def visitTestDecl(cls, node, module, semantic):
        pass

    @dispatch(parser.ImportDecl)
    def visitImportDecl(cls, node, module, semantic):
        dotted = '.'.join(node.path)
        semantic.register(node.loc, node.path[-1], semantic.modules[dotted])

    @dispatch(parser.FuncDecl)
    def visitFuncDecl(cls, node, module, semantic):
        loc = node.name.loc
        name = node.name.text
        f = model.Function(loc, name, module)
        semantic.register(loc, name, f)
        return f

    @dispatch(parser.StructDecl)
    def visitStructDecl(cls, node, module, semantic):
        loc = node.name.loc
        name = node.name.text
        s = model.Struct(loc, name, node.is_ref, module, model.UserTypeTag())
        semantic.register(loc, name, s)

        fields = []
        methods = []
        for m in node.members:
            loc = m.name.loc
            name = m.name.text
            if name in s.namespace:
                semantic.status.error('tried to redefine "%s"' % name, loc)

            if isinstance(m, parser.FuncDecl):
                f = model.Function(loc, name, module)
                methods.append(f)
                s.namespace[name] = f
            elif isinstance(m, parser.FieldDecl):
                f = model.Field(loc, name, s)
                fields.append(f)
                s.namespace[name] = f
            else:
                assert False, m

        s.fields = fields
        s.methods = methods
        return s

    @dispatch(parser.ExternFuncDecl)
    def visitExternFuncDecl(cls, node, module, semantic):
        loc = node.name.loc
        name = node.name.text
        f = model.ExternFunction(loc, name, module)
        semantic.register(loc, name, f)
        return f

    @dispatch(parser.Module)
    def visitModule(cls, node, module, semantic):
        structs = []
        extern_funcs = []
        funcs = []
        tests = []
        with semantic.namespace(module.namespace):
            for decl in node.decls:
                obj = cls.visit(decl, module, semantic)
                if obj is None:
                    pass
                elif isinstance(obj, model.Struct):
                    structs.append(obj)
                elif isinstance(obj, model.ExternFunction):
                    extern_funcs.append(obj)
                elif isinstance(obj, model.Function):
                    funcs.append(obj)
                elif isinstance(obj, model.Test):
                    tests.append(obj)
                else:
                    assert False, obj

        module.structs = structs
        module.extern_funcs = extern_funcs
        module.funcs = funcs


class ResolveType(object, metaclass=TypeDispatcher):

    @dispatch(parser.NamedTypeRef)
    def visitNamedTypeRef(self, node, semantic):
        loc = node.name.loc
        name = node.name.text
        obj = semantic.lookup(name)
        if obj is None:
            semantic.status.error('cannot resolve "%s"' % name, loc)
            return POISON_TYPE
        if not isinstance(obj, model.Type):
            semantic.status.error('"%s" does not refer to a type' % name, loc)
            return POISON_TYPE
        return obj


class ResolveInheritance(object, metaclass=TypeDispatcher):

    @dispatch(parser.ImportDecl, parser.TestDecl, parser.FuncDecl, parser.ExternFuncDecl)
    def visitLeaf(cls, node, module, semantic):
        pass

    @dispatch(parser.StructDecl)
    def visitStructDecl(cls, node, module, semantic):
        s = module.namespace[node.name.text]
        loc = s.loc
        if not isinstance(node.parent, parser.NoTypeRef):
            parent = ResolveType.visit(node.parent, semantic)
            if isinstance(parent, model.Struct):
                s.parent = parent
            elif isinstance(parent, model.PoisonType):
                pass
            else:
                semantic.status.error('cannot inherit from %s' % PrintableTypeName.visit(parent), loc)
            if s.is_ref != parent.is_ref:
                semantic.status.error('mismatched inheritance or ref type vs. value type', loc, [parent.loc])

    @dispatch(parser.Module)
    def visitModule(cls, node, module, semantic):
        with semantic.namespace(module.namespace):
            for decl in node.decls:
                cls.visit(decl, module, semantic)


def struct_lookup(s, name):
    while s:
        if name in s.namespace:
            return s.namespace[name]
        s = s.parent
    return None


def all_fields(s):
    parent_fields = all_fields(s.parent) if s.parent else []
    return parent_fields + s.fields


class ResolveSignatures(object, metaclass=TypeDispatcher):

    @dispatch(parser.FuncDecl)
    def visitFuncDecl(cls, node, f, semantic):
        pt = []
        for p in node.params:
            loc = p.name.loc
            name = p.name.text
            t = ResolveType.visit(p.t, semantic)
            pt.append(t)
            f.params.append(model.Param(loc, name, t))

        rt = []
        for r in node.returns:
            t = ResolveType.visit(r, semantic)
            rt.append(t)
        f.t = make_function_type(pt, rt, semantic)

    @dispatch(parser.StructDecl)
    def visitStructDecl(cls, node, s, semantic):
        for m in node.members:
            loc = m.name.loc
            name = m.name.text

            f = s.namespace[name]

            if s.parent:
                shadowing = struct_lookup(s.parent, name)
                if shadowing:
                    if isinstance(f, model.BaseFunction) and isinstance(shadowing, model.BaseFunction):
                        f.overrides = shadowing
                        shadowing.is_overridden = True
                    else:
                        semantic.status.error('"%s" shadows an existing name' % name, loc, [shadowing.loc])

            if isinstance(m, parser.FuncDecl):
                cls.visit(m, f, semantic)
            elif isinstance(m, parser.FieldDecl):
                f.t = ResolveType.visit(m.t, semantic)
            else:
                assert False, m

    @dispatch(parser.ExternFuncDecl)
    def visitExternFuncDecl(cls, node, f, semantic):
        pt = []
        for p in node.params:
            loc = p.name.loc
            name = p.name.text
            t = ResolveType.visit(p.t, semantic)
            pt.append(t)
            p = model.Param(loc, name, t)
            f.params.append(p)

        rt = []
        for r in node.returns:
            t = ResolveType.visit(r, semantic)
            rt.append(t)
        f.t = make_function_type(pt, rt, semantic)

    @dispatch(parser.Module)
    def visitModule(cls, node, module, semantic):
        with semantic.namespace(module.namespace):
            for decl in node.decls:
                if isinstance(decl, (parser.ImportDecl, parser.TestDecl)):
                    continue
                obj = module.namespace[decl.name.text]
                cls.visit(decl, obj, semantic)


# TODO: better names for constant modules, etc.
class PrintableTypeName(object, metaclass=TypeDispatcher):

    @dispatch(model.Struct)
    def visitStruct(cls, node):
        return node.name

    @dispatch(model.TupleType)
    def visitTupleType(cls, node):
        return '(%s)' % ', '.join([cls.visit(arg) for arg in node.children])

    @dispatch(model.ModuleType)
    def visitModuleType(cls, node):
        return 'module'


def wrap_obj(loc, obj):
    if isinstance(obj, model.Local):
        return model.GetLocal(loc, obj, obj.t), obj.t
    elif isinstance(obj, model.Type):
        return model.GetType(loc, obj), obj
    elif isinstance(obj, model.Function):
        return model.GetFunction(loc, obj), obj.t
    elif isinstance(obj, model.ExternFunction):
        return model.GetFunction(loc, obj), obj.t
    elif isinstance(obj, model.Module):
        return model.GetModule(loc, obj), MODULE_TYPE
    else:
        assert False, obj


def can_hold(a, b):
    if a is b:
        return True
    if isinstance(a, model.PoisonType) or isinstance(b, model.PoisonType):
        return True
    if isinstance(a, model.Struct) and isinstance(b, model.Struct):
        if b.parent:
            return can_hold(a, b.parent)
    if isinstance(a, model.TupleType) and isinstance(b, model.TupleType):
        if len(a.children) != len(b.children):
            return False
        # TODO not quite right, should be checking exact equality.
        for ac, bc in zip(a.children, b.children):
            if not can_hold(ac, bc):
                return False
        return True
    return False


def flatten_inheritance(s):
    if s.parent:
        return flatten_inheritance(s.parent) + [s]
    else:
        return [s]


def unify_type_pair(a, b):
    if a is b:
        return a
    if isinstance(a, model.Struct) and isinstance(b, model.Struct):
        ai = flatten_inheritance(a)
        bi = flatten_inheritance(b)
        prev = None
        for ap, bp in zip(ai, bi):
            if ap is not bp:
                break
            prev = ap
        return prev
    return None


def unify_types(loc, used, types, semantic):
    if not used or not types:
        return VOID_TYPE

    t = types[0]
    if t is POISON_TYPE:
        return POISON_TYPE

    for other in types[1:]:
        if other is POISON_TYPE:
            return POISON_TYPE

        next = unify_type_pair(t, other)
        if next is None:
            semantic.status.error('cannot unify types %s and %s' % (PrintableTypeName.visit(t), PrintableTypeName.visit(other)), loc)
            return POISON_TYPE
        t = next
    return t


def check_can_hold(loc, a, b, semantic):
    assert isinstance(loc, int), loc
    assert isinstance(a, model.Type), a
    assert isinstance(b, model.Type), b
    ok = can_hold(a, b)
    if not ok:
        semantic.status.error('expected type %s, but got %s' % (PrintableTypeName.visit(a), PrintableTypeName.visit(b)), loc)
    return ok


class ResolveAssignmentTarget(object, metaclass=TypeDispatcher):

    @dispatch(parser.GetName)
    def visitGetName(cls, node, value_type, is_let, semantic):
        loc = node.name.loc
        name = node.name.text
        if is_let:
            lcl = semantic.define_lcl(loc, name, value_type)
            if not lcl:
                return POISON_TARGET, True
            return model.SetLocal(loc, lcl), True
        else:
            obj = semantic.lookup(name)
            if obj is None:
                semantic.status.error('cannot resolve "%s"' % name, loc)
                return POISON_TARGET, False
            if not isinstance(obj, model.Local):
                # TODO metter naming?
                semantic.status.error('cannot assign to %s' % type(obj).__name__, loc)
                return POISON_TARGET, False
            check_can_hold(loc, obj.t, value_type, semantic)
            return model.SetLocal(loc, obj), False

    @dispatch(parser.GetAttr)
    def visitGetAttr(cls, node, value_type, is_let, semantic):
        loc = node.loc
        name = node.name.text
        expr, t = ResolveCode.visit(node.expr, True, semantic)
        if isinstance(t, model.PoisonType):
            return POISON_TARGET, False
        elif isinstance(t, model.Struct):
            f = struct_lookup(t, name)
            if f is None:
                semantic.status.error('cannot set attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
                return POISON_TARGET, False
            return model.SetField(loc, expr, f), False
        else:
            semantic.status.error('cannot set attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
            return POISON_TARGET, False

    @dispatch(parser.Let)
    def visitLet(cls, node, value_type, is_let, semantic):
        if is_let:
            semantic.status.error('redundant "let"', node.loc)
        tgt, defines = cls.visit(node.expr, value_type, True, semantic)
        if not defines:
            semantic.status.error('"let" does not define a new variable', node.loc)
        return tgt, defines

    @dispatch(parser.TupleLiteral)
    def visitTupleLiteral(cls, node, value_type, is_let, semantic):
        loc = node.loc

        if isinstance(value_type, model.TupleType):
            if len(node.args) == len(value_type.children):
                args = []
                defines = False
                for i in range(len(node.args)):
                    arg = node.args[i]
                    arg_t = value_type.children[i]
                    arg, arg_defines = cls.visit(arg, arg_t, is_let, semantic)
                    defines |= arg_defines
                    args.append(arg)
                return model.DestructureTuple(loc, args), defines
            else:
                semantic.status.error('expected tuple of length %d, but got %d' % (len(node.args), len(value_type.children)), loc)
        elif isinstance(value_type, model.Struct):
            # Flatten fields.
            all_fields = value_type.fields
            parent = value_type.parent
            while parent:
                all_fields = parent.fields + all_fields
                parent = parent.parent

            if len(node.args) == len(all_fields):
                args = []
                defines = False
                for i in range(len(node.args)):
                    arg = node.args[i]
                    arg_t = all_fields[i].t
                    arg, arg_defines = cls.visit(arg, arg_t, is_let, semantic)
                    defines |= arg_defines
                    args.append(arg)
                return model.DestructureStruct(loc, value_type, args), defines
            else:
                semantic.status.error('expected structure with %d fields, but %s has %d fields' % (len(node.args), PrintableTypeName.visit(value_type), len(all_fields)), loc)
        elif not isinstance(value_type, model.PoisonType):
            semantic.status.error('cannot destructure %s as a tuple' % (PrintableTypeName.visit(value_type)), loc)

        # Can't validate the destructuring, so validate the children as much as we can and then fail.
        defines = False
        for arg in node.args:
            _, arg_defines = cls.visit(arg, POISON_TYPE, is_let, semantic)
            defines |= arg_defines
        return POISON_TARGET, defines


class ResolveMatcher(object, metaclass=TypeDispatcher):

    @dispatch(parser.StructMatch)
    def visitStructMatch(cls, node, t, semantic):
        mt = ResolveType.visit(node.t, semantic)
        check_can_hold(node.t.name.loc, t, mt, semantic)
        return model.StructMatch(mt)


class ResolveCode(object, metaclass=TypeDispatcher):

    @classmethod
    def visit_expr_list(cls, exprs, semantic):
        values = []
        types = []
        for e in exprs:
            v, t = cls.visit(e, True, semantic)
            values.append(v)
            types.append(t)
        return values, types

    @classmethod
    def do_get_attr(cls, loc, expr, t, name, semantic):
        if isinstance(t, model.PoisonType):
            return POISON_EXPR, POISON_TYPE
        elif isinstance(t, model.ModuleType):
            m = expr.m
            obj = m.namespace.get(name)
            if obj is None:
                semantic.status.error('cannot get attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
                return POISON_EXPR, POISON_TYPE
            return wrap_obj(loc, obj)
        elif isinstance(t, model.Struct):
            f = struct_lookup(t, name)
            if f is None:
                semantic.status.error('cannot get attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
                return POISON_EXPR, POISON_TYPE
            if isinstance(f, model.Field):
                return model.GetField(loc, expr, f, f.t), f.t
            elif isinstance(f, model.BaseFunction):
                return model.GetMethod(loc, expr, f), f.t
            else:
                assert False, f
        else:
            semantic.status.error('cannot get attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
            return POISON_EXPR, POISON_TYPE

    @classmethod
    def do_call(cls, loc, expr, et, arg_exprs, arg_types, semantic):
        if isinstance(et, model.PoisonType):
            return POISON_EXPR, POISON_TYPE

        arg_count = len(arg_exprs)

        if isinstance(et, model.FunctionType):
            # TODO overloads?
            params = et.params
            if len(params) != arg_count:
                semantic.status.error('expected %d arguments, got %d' % (len(params), arg_count), loc)
                return POISON_EXPR, POISON_TYPE

            for i in range(arg_count):
                pt = et.params[i]
                ae = arg_exprs[i]
                at = arg_types[i]
                if not isinstance(ae, model.PoisonExpr):
                    check_can_hold(ae.loc, pt, at, semantic)

            if isinstance(expr, model.GetFunction):
                return model.DirectCall(loc, expr.f, arg_exprs, et.rt), et.rt
            elif isinstance(expr, model.GetMethod):
                f = expr.func
                if f.is_overridden:
                    return model.IndirectMethodCall(loc, expr.expr, f.name, arg_exprs, et.rt), et.rt
                else:
                   return model.DirectMethodCall(loc, expr.expr, f, arg_exprs, et.rt), et.rt
            else:
                assert False, expr
        elif isinstance(et, model.Struct):
            fields = all_fields(et)
            if len(fields) != arg_count:
                semantic.status.error('expected %d arguments, got %d' % (len(fields), arg_count), loc)
                return POISON_EXPR, POISON_TYPE

            for i in range(arg_count):
                pt = fields[i].t
                ae = arg_exprs[i]
                at = arg_types[i]
                check_can_hold(ae.loc, pt, at, semantic)

            if isinstance(expr, model.GetType):
                return model.Constructor(loc, expr.t, arg_exprs), et
            else:
                assert False, expr
        else:
            semantic.status.error('cannot call %s' % (PrintableTypeName.visit(et)), loc)
            return POISON_EXPR, POISON_TYPE

    @dispatch(parser.BooleanLiteral)
    def visitBooleanLiteral(cls, node, used, semantic):
        t = semantic.builtins['bool']
        return model.BooleanLiteral(node.loc, node.value, t), t

    @dispatch(parser.IntLiteral)
    def visitIntLiteral(cls, node, used, semantic):
        loc = node.loc
        t = semantic.builtins[node.postfix]
        value = int(node.text, node.base)

        if t.name.startswith('f'):
            return model.FloatLiteral(loc, value), t
        else:
            # Need to be a little conservative because we don't know if it's a negative literal or not.
            bits = t.tag.width if t.tag.unsigned else t.tag.width - 1
            if value > 2**bits:
                semantic.status.error('literal of type %s is out of range' % PrintableTypeName.visit(t), loc)
                return POISON_EXPR, t
            return model.IntLiteral(loc, value, t), t

    @dispatch(parser.FloatLiteral)
    def visitFloatLiteral(cls, node, used, semantic):
        loc = node.loc
        t = semantic.builtins[node.postfix]
        assert t.name.startswith('f'), t
        # TODO error handling.
        text = node.text
        value = float(node.text)
        # TODO flexible types?
        return model.FloatLiteral(loc, text, value, t), t

    @dispatch(parser.StringLiteral)
    def visitStringLiteral(cls, node, used, semantic):
        t = semantic.builtins['string']
        return model.StringLiteral(node.loc, node.value, t), t

    @dispatch(parser.StringConcat)
    def visitStringConcat(cls, node, used, semantic):
        t = semantic.builtins['string']
        if len(node.children) == 0:
            return model.StringLiteral(node.loc, "", t), t

        arg_exprs, arg_types = cls.visit_expr_list(node.children, semantic)

        coerced = []
        poisoned = False
        for arg_expr, arg_t in zip(arg_exprs, arg_types):
            if isinstance(arg_t, model.PoisonType):
                poisoned = True
                continue
            # Coerce to string?
            if arg_t != t:
                # Get to_string.
                attr_expr, attr_t = cls.do_get_attr(arg_expr.loc, arg_expr, arg_t, 'to_string', semantic)
                if isinstance(attr_t, model.PoisonType):
                    poisoned = True
                    continue
                # Call the result.
                coerce_expr, coerce_t = cls.do_call(attr_expr.loc, attr_expr, attr_t, [], [], semantic)
                if isinstance(coerce_t, model.PoisonType):
                    poisoned = True
                    continue
                # Is the interface right?
                if coerce_t != t:
                    semantic.status.error(f'.to_string() did not coerce {PrintableTypeName.visit(arg_t)} into a string', coerce_expr.loc)
                    poisoned = True
                    continue
                arg_expr = coerce_expr
                arg_t = coerce_t

            coerced.append(arg_expr)

        if poisoned:
            return POISON_EXPR, POISON_TYPE

        # Concatinate the strings.
        expr = coerced.pop(0)
        while coerced:
            expr = model.BinaryOp(node.loc, expr, '+', coerced.pop(0), t)

        return expr, t

    @dispatch(parser.GetName)
    def visitGetName(cls, node, used, semantic):
        loc = node.name.loc
        name = node.name.text
        obj = semantic.lookup(name)
        if obj is None:
            semantic.status.error('cannot resolve "%s"' % name, loc)
            return POISON_EXPR, POISON_TYPE
        return wrap_obj(loc, obj)

    @dispatch(parser.GetAttr)
    def visitGetAttr(cls, node, used, semantic):
        loc = node.loc
        name = node.name.text
        expr, t = cls.visit(node.expr, True, semantic)
        assert isinstance(t, model.Type), (node, expr, t)

        return cls.do_get_attr(loc, expr, t, name, semantic)

    @dispatch(parser.Call)
    def visitCall(cls, node, used, semantic):
        loc = node.loc
        expr, et = cls.visit(node.expr, True, semantic)
        arg_exprs, arg_types = cls.visit_expr_list(node.args, semantic)
        return cls.do_call(loc, expr, et, arg_exprs, arg_types, semantic)


    @dispatch(parser.TupleLiteral)
    def visitTupleLiteral(cls, node, used, semantic):
        arg_exprs, arg_types = cls.visit_expr_list(node.args, semantic)
        t = make_tuple_type(arg_types, semantic)
        return model.TupleLiteral(node.loc, t, arg_exprs), t

    @dispatch(parser.Assign)
    def visitAssign(cls, node, used, semantic):
        value, vt = cls.visit(node.value, True, semantic)
        target, _ = ResolveAssignmentTarget.visit(node.target, vt, False, semantic)
        return model.Assign(node.loc, target, value), VOID_TYPE

    @dispatch(parser.Sequence)
    def visitSequence(cls, node, used, semantic):
        children = []
        if node.children:
            for child in node.children[:-1]:
                child, _ = cls.visit(child, False, semantic)
                children.append(child)
            child, t = cls.visit(node.children[-1], True, semantic)
            children.append(child)
        else:
            t = VOID_TYPE
        # HACK
        loc = children[-1].loc if children and hasattr(children[-1], 'loc') else -1
        return model.Sequence(loc, children, t), t

    @dispatch(parser.PrefixOp)
    def visitPrefixOp(cls, node, used, semantic):
        loc = node.loc
        expr, t = cls.visit(node.expr, used, semantic)
        if node.op == '!':
            t = semantic.builtins['bool']
        return model.PrefixOp(loc, node.op, expr, t), t

    @dispatch(parser.BinaryOp)
    def visitBinaryOp(cls, node, used, semantic):
        loc = node.loc
        l, lt = cls.visit(node.left, True, semantic)
        r, rt = cls.visit(node.right, True, semantic)
        # TODO better validation and checking.
        check_can_hold(node.right.loc, lt, rt, semantic)
        if node.op in set(['<=', '<', '>=', '>', '==', '!=']):
            t = semantic.builtins['bool']
        else:
            t = lt
        return model.BinaryOp(loc, l, node.op, r, t), t

    @dispatch(parser.If)
    def visitIf(cls, node, used, semantic):
        loc = node.loc
        cond, ct = cls.visit(node.cond, True, semantic)
        check_can_hold(node.cond.loc, semantic.builtins['bool'], ct, semantic)
        te, tt = cls.visit(node.t, used, semantic)
        fe, ft = cls.visit(node.f, used, semantic)

        rt = unify_types(loc, used, [tt, ft], semantic)
        return model.If(loc, cond, te, fe, rt), rt

    @dispatch(parser.While)
    def visitWhile(cls, node, used, semantic):
        cond, ct = cls.visit(node.cond, True, semantic)
        check_can_hold(node.cond.loc, semantic.builtins['bool'], ct, semantic)
        body, _ = cls.visit(node.body, False, semantic)
        return model.While(node.loc, cond, body), VOID_TYPE

    @dispatch(parser.Match)
    def visitMatch(cls, node, used, semantic):
        cond, ct = cls.visit(node.cond, True, semantic)
        cases = []
        types = []
        for case in node.cases:
            m = ResolveMatcher.visit(case.matcher, ct, semantic)
            e, et = cls.visit(case.expr, used, semantic)
            cases.append(model.Case(case.loc, m, e))
            types.append(et)
        rt = unify_types(node.loc, used, types, semantic)
        return model.Match(node.loc, cond, cases, rt), rt

    @dispatch(parser.FuncDecl)
    def visitFuncDecl(cls, node, f, semantic, struct=None):
        ns = OrderedDict()
        semantic.func = f
        with semantic.namespace(ns):
            if struct:
                name = 'self'
                p = model.Param(f.loc, name, struct)
                p.lcl = semantic.define_lcl(f.loc, name, struct)
                f.self = p

            for p in f.params:
                p.lcl = semantic.define_lcl(p.loc, p.name, p.t)

            used = True
            f.body, t = cls.visit(node.body, used, semantic)

            if not isinstance(t, model.PoisonType):
                # TODO: break down tuple checks.
                check_can_hold(f.body.loc, f.t.rt, t, semantic)

        semantic.func = None

    @dispatch(parser.ExternFuncDecl)
    def visitExternFuncDecl(cls, node, module, semantic):
        pass

    @dispatch(parser.TestDecl)
    def visitTestDecl(cls, node, module, semantic):
        t = model.Test(node.desc)
        ns = OrderedDict()
        semantic.func = t
        with semantic.namespace(ns):
            t.body, _ = cls.visit(node.body, False, semantic)
        semantic.func = None
        module.tests.append(t)

    @dispatch(parser.StructDecl)
    def visitStruct(cls, node, s, semantic):
        for m in node.members:
            if isinstance(m, parser.FuncDecl):
                f = s.namespace[m.name.text]
                cls.visit(m, f, semantic, s)

    @dispatch(parser.Module)
    def visitModule(cls, node, module, semantic):
        with semantic.namespace(module.namespace):
            for decl in node.decls:
                if isinstance(decl, parser.ImportDecl):
                    continue
                if isinstance(decl, parser.TestDecl):
                    cls.visit(decl, module, semantic)
                else:
                    obj = module.namespace[decl.name.text]
                    cls.visit(decl, obj, semantic)


def check_for_type_loops(p, status):
    def check_struct(s):
        if s in started:
            if s not in completed:
                l = len(stack)
                for i in range(l-1, -1, -1):
                    f = stack[i]
                    if f is s or isinstance(f, model.Field) and f.owner is s:
                        break
                status.error("structure embedding is recursive", s.loc, [f.loc for f in stack[i:]])
            return
        else:
            started.add(s)
            # Inheritance is essentially embedding.
            p = s.parent
            if p:
                stack.append(s)
                check_struct(p)
                stack.pop()
            # Fields
            for f in s.fields:
                if isinstance(f.t, model.Struct) and not f.t.is_ref:
                    stack.append(f)
                    check_struct(f.t)
                    stack.pop()
            completed.add(s)

    started = set()
    completed = set()
    stack = []
    for m in p.modules:
        for s in m.structs:
            check_struct(s)


def init_builtins(ns, semantic):
    builtin = model.Module('builtin')

    def make(name, tag):
        s = model.Struct(0, name, False, builtin, tag)
        ns[name] = s

        f = model.ExternFunction(0, 'to_string', builtin)
        f.self = model.Param(0, 'self', s)
        f.t = make_function_type([], [ns['string']], semantic)

        s.methods.append(f)
        s.namespace[f.name] = f
        builtin.extern_funcs.append(f)

        return s

    make('string', model.IntrinsicTypeTag('string'))
    make('bool', model.IntrinsicTypeTag('bool'))

    # Integers
    for w in [8, 16, 32, 64]:
        # Signed
        name = 'i%d' % w
        make(name, model.IntegerTypeTag(name, w, False))

        #Unsigned
        name = 'u%d' % w
        make(name, model.IntegerTypeTag(name, w, True))

    # Floats
    for w in [32, 64]:
        name = 'f%d' % w
        make(name, model.FloatTypeTag(name, w))

    return builtin

def process(modules, status):
    semantic = SemanticPass(status)
    module = init_builtins(semantic.builtins, semantic)

    # Create module objects
    p = model.Program()

    # Register builtins
    semantic.modules[module.name] = module
    p.modules.append(module)

    for m in modules:
        module = model.Module(m.name)
        assert m.name not in semantic.modules, m.name
        semantic.modules[m.name] = module
        p.modules.append(module)

    # Create the objects contained in each module.
    for m in modules:
        module = semantic.modules[m.name]
        IndexNamespace.visit(m, module, semantic)
    status.halt_if_errors()

    # Resolve type inheritance.
    for m in modules:
        module = semantic.modules[m.name]
        ResolveInheritance.visit(m, module, semantic)
    status.halt_if_errors()

    # Evaluate without fields to check for inheritance loops.
    # Inheritance loops can make field lookups hang.
    check_for_type_loops(p, status)
    status.halt_if_errors()

    # Resolve field and parameter types.
    for m in modules:
        module = semantic.modules[m.name]
        ResolveSignatures.visit(m, module, semantic)
    status.halt_if_errors()

    # Now that field are resolved, check there are no loops in value type embedding.
    check_for_type_loops(p, status)
    status.halt_if_errors()

    # Resolve function bodies.
    for m in modules:
        module = semantic.modules[m.name]
        ResolveCode.visit(m, module, semantic)
    status.halt_if_errors()

    return p
