from ritual.base import TypeDispatcher, dispatch
from collections import OrderedDict
import model
import parser

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
                    semantic.status.error('tried to redefine "%s"' % name, loc)
                else:
                    semantic.status.error('"%s" shadows an existing name' % name, loc)
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


class IndexNamespace(object):
    __metaclass__ = TypeDispatcher

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
        s = model.Struct(loc, name, node.is_ref, module)
        semantic.register(loc, name, s)
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


class ResolveType(object):
    __metaclass__ = TypeDispatcher

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


class ResolveSignatures(object):
    __metaclass__ = TypeDispatcher

    @dispatch(parser.ImportDecl, parser.TestDecl)
    def visitLeaf(cls, node, module, semantic):
        pass

    @dispatch(parser.FuncDecl)
    def visitFuncDecl(cls, node, module, semantic):
        f = module.namespace[node.name.text]
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
    def visitStructDecl(cls, node, module, semantic):
        s = module.namespace[node.name.text]
        fields = []
        for fd in node.fields:
            loc = fd.name.loc
            name = fd.name.text
            f = model.Field(loc, name, ResolveType.visit(fd.t, semantic), s)
            fields.append(f)
            if name in s.namespace:
                semantic.status.error('tried to redefine "%s"' % name, loc)
            s.namespace[name] = f
        s.fields = fields

    @dispatch(parser.ExternFuncDecl)
    def visitExternFuncDecl(cls, node, module, semantic):
        f = module.namespace[node.name.text]
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
                cls.visit(decl, module, semantic)


class PrintableTypeName(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.IntrinsicType)
    def visitIntrinsicType(cls, node):
        return node.name

    @dispatch(model.Struct)
    def visitStruct(cls, node):
        return node.name

    @dispatch(model.TupleType)
    def visitTupleType(cls, node):
        return '(%s)' % ', '.join([cls.visit(arg) for arg in node.children])


def wrap_obj(loc, obj):
    if isinstance(obj, model.Local):
        return model.GetLocal(loc, obj), obj.t
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
    if isinstance(a, model.IntrinsicType) and isinstance(b, model.IntrinsicType):
        return a.name == b.name
    if isinstance(a, model.TupleType) and isinstance(b, model.TupleType):
        if len(a.children) != len(b.children):
            return False
        # TODO not quite right, should be checking exact equality.
        for ac, bc in zip(a.children, b.children):
            if not can_hold(ac, bc):
                return False
        return True
    return False

def check_can_hold(loc, a, b, semantic):
    assert isinstance(loc, int), loc
    assert isinstance(a, model.Type), a
    assert isinstance(b, model.Type), b
    ok = can_hold(a, b)
    if not ok:
        semantic.status.error('expected type %s, but got %s' % (PrintableTypeName.visit(a), PrintableTypeName.visit(b)), loc)
    return ok


class ResolveAssignmentTarget(object):
    __metaclass__ = TypeDispatcher

    @dispatch(parser.GetName)
    def visitGetName(cls, node, value_type, is_let, semantic):
        loc = node.name.loc
        name = node.name.text
        if is_let:
            lcl = semantic.define_lcl(loc, name, value_type)
            if not lcl:
                return POISON_TARGET
            return model.SetLocal(loc, lcl)
        else:
            obj = semantic.lookup(name)
            if obj is None:
                semantic.status.error('cannot resolve "%s"' % name, loc)
                return POISON_TARGET
            if not isinstance(obj, model.Local):
                # TODO metter naming?
                semantic.status.error('cannot assign to %s' % type(obj).__name__, loc)
                return POISON_TARGET
            check_can_hold(loc, obj.t, value_type, semantic)
            return model.SetLocal(loc, obj)

    @dispatch(parser.GetAttr)
    def visitGetAttr(cls, node, value_type, is_let, semantic):
        loc = node.loc
        name = node.name.text
        expr, t = ResolveCode.visit(node.expr, True, semantic)
        if isinstance(t, model.PoisonType):
            return POISON_TARGET
        elif isinstance(t, model.Struct):
            f = t.namespace.get(name)
            if f is None:
                semantic.status.error('cannot set attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
                return POISON_TARGET
            return model.SetField(loc, expr, f)
        else:
            semantic.status.error('cannot set attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
            return POISON_TARGET

    @dispatch(parser.Let)
    def visitLet(cls, node, value_type, is_let, semantic):
        if is_let:
            semantic.status.error('redundant let', node.loc)
        return cls.visit(node.expr, value_type, True, semantic)

    @dispatch(parser.TupleLiteral)
    def visitTupleLiteral(cls, node, value_type, is_let, semantic):
        loc = node.loc
        ok = False
        if isinstance(value_type, model.PoisonType):
            pass
        elif not isinstance(value_type, model.TupleType):
            semantic.status.error('expected tuple, but got %s' % (PrintableTypeName.visit(value_type)), loc)
        elif len(node.args) != len(value_type.children):
            semantic.status.error('expected tuple of length %d, but got %d' % (len(node.args), len(value_type.children)), loc)
        else:
            ok = True

        args = []
        for i in range(len(node.args)):
            arg = node.args[i]
            arg_t = value_type.children[i] if ok else POISON_TYPE
            args.append(cls.visit(arg, arg_t, is_let, semantic))

        return model.DestructureTuple(loc, args)


class ResolveCode(object):
    __metaclass__ = TypeDispatcher

    @classmethod
    def visit_expr_list(cls, exprs, semantic):
        values = []
        types = []
        for e in exprs:
            v, t = cls.visit(e, True, semantic)
            values.append(v)
            types.append(t)
        return values, types

    @dispatch(parser.ImportDecl, parser.StructDecl)
    def visitLeaf(cls, node, module, semantic):
        pass

    @dispatch(parser.IntLiteral)
    def visitIntLiteral(cls, node, used, semantic):
        loc = node.loc
        # TODO error handling.
        value = int(node.text, node.base)
        # TODO flexible integer types?
        return model.IntLiteral(loc, value), semantic.builtins['i32']

    @dispatch(parser.FloatLiteral)
    def visitFloatLiteral(cls, node, used, semantic):
        loc = node.loc
        # TODO error handling.
        text = node.text
        value = float(node.text)
        # TODO flexible types?
        return model.FloatLiteral(loc, text, value), semantic.builtins['f32']


    @dispatch(parser.StringLiteral)
    def visitStringLiteral(cls, node, used, semantic):
        return model.StringLiteral(node.loc, node.value), semantic.builtins['string']

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
            f = t.namespace.get(name)
            if f is None:
                semantic.status.error('cannot get attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
                return POISON_EXPR, POISON_TYPE
            return model.GetField(loc, expr, f), f.t
        else:
            semantic.status.error('cannot get attribute "%s" of %s' % (name, PrintableTypeName.visit(t)), loc)
            return POISON_EXPR, POISON_TYPE

    @dispatch(parser.Call)
    def visitCall(cls, node, used, semantic):
        loc = node.loc
        expr, et = cls.visit(node.expr, True, semantic)
        arg_exprs, arg_types = cls.visit_expr_list(node.args, semantic)

        if isinstance(et, model.PoisonType):
            return POISON_EXPR, POISON_TYPE

        arg_count = len(node.args)

        if isinstance(et, model.FunctionType):
            # TODO overloads?
            params = et.params
            if len(params) != arg_count:
                semantic.status.error('expected %d arguments, got %d' % (len(params), arg_count, loc))
                return POISON_EXPR, POISON_TYPE

            for i in range(arg_count):
                pt = et.params[i]
                ae = arg_exprs[i]
                at = arg_types[i]
                check_can_hold(ae.loc, pt, at, semantic)

            if isinstance(expr, model.GetFunction):
                return model.DirectCall(loc, expr.f, arg_exprs), et.rt
            else:
                assert False, expr
        elif isinstance(et, model.Struct):
            fields = et.fields
            if len(fields) != arg_count:
                semantic.status.error('expected %d arguments, got %d' % (len(fields), arg_count, loc))
                return POISON_EXPR, POISON_TYPE
            
            for i in range(arg_count):
                pt = et.fields[i].t
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


    @dispatch(parser.TupleLiteral)
    def visitTupleLiteral(cls, node, used, semantic):
        arg_exprs, arg_types = cls.visit_expr_list(node.args, semantic)
        t = make_tuple_type(arg_types, semantic)
        return model.TupleLiteral(node.loc, t, arg_exprs), t

    @dispatch(parser.Assign)
    def visitAssign(cls, node, used, semantic):
        value, vt = cls.visit(node.value, True, semantic)
        target = ResolveAssignmentTarget.visit(node.target, vt, False, semantic)
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
        return model.Sequence(loc, children), t

    @dispatch(parser.PrefixOp)
    def visitPrefixOp(cls, node, used, semantic):
        loc = node.loc
        expr, t = cls.visit(node.expr, used, semantic)
        return model.PrefixOp(loc, node.op, expr), t

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
        return model.BinaryOp(loc, l, node.op, r), t

    @dispatch(parser.While)
    def visitWhile(cls, node, used, semantic):
        cond, ct = cls.visit(node.cond, True, semantic)
        check_can_hold(node.cond.loc, semantic.builtins['bool'], ct, semantic)
        body, _ = cls.visit(node.body, False, semantic)
        return model.While(node.loc, cond, body), VOID_TYPE

    @dispatch(parser.FuncDecl)
    def visitFuncDecl(cls, node, module, semantic):
        f = module.namespace[node.name.text]
        ns = OrderedDict()
        semantic.func = f
        with semantic.namespace(ns):
            for p in f.params:
                p.lcl = semantic.define_lcl(p.loc, p.name, p.t)

            used = True
            f.body, t = cls.visit(node.body, used, semantic)

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

    @dispatch(parser.Module)
    def visitModule(cls, node, module, semantic):
        with semantic.namespace(module.namespace):
            for decl in node.decls:
                cls.visit(decl, module, semantic)


def process(modules, status):
    semantic = SemanticPass(status)

    ns = semantic.builtins
    ns['bool'] = model.IntrinsicType('bool')
    ns['i8'] = model.IntrinsicType('i8')
    ns['i16'] = model.IntrinsicType('i16')
    ns['i32'] = model.IntrinsicType('i32')
    ns['f32'] = model.IntrinsicType('f32')
    ns['f64'] = model.IntrinsicType('f64')

    ns['string'] = model.IntrinsicType('string')

    # Create objects
    p = model.Program()
    for m in modules:
        module = model.Module(m.name)
        assert m.name not in semantic.modules, m.name
        semantic.modules[m.name] = module
        p.modules.append(module)

    for m in modules:
        module = semantic.modules[m.name]
        IndexNamespace.visit(m, module, semantic)
    status.halt_if_errors()

    for m in modules:
        module = semantic.modules[m.name]
        ResolveSignatures.visit(m, module, semantic)
    status.halt_if_errors()

    for m in modules:
        module = semantic.modules[m.name]
        ResolveCode.visit(m, module, semantic)
    status.halt_if_errors()

    return p
