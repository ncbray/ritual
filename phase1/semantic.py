from base import TypeDispatcher, dispatch
import interpreter
import model


def cached_list_type(t):
    assert hasattr(t, 'list_cache'), t
    if t.list_cache is None:
        t.list_cache = model.ListType(t)
    return t.list_cache


def can_hold(general, specific):
    if general is specific:
        return True
    elif isinstance(general, model.UnionType):
        for t in general.types:
            if can_hold(t, specific):
                return True
        return False
    return False


class LocalSlot(object):
    def __init__(self, t):
        self.t = t


class SemanticPass(object):
    def __init__(self, status):
        self.status = status
        self.scope_name = 'global'
        self.globals = {}
        self.global_refs = set()
        self.locals = {}

        self.void = model.VoidType()
        self.intrinsics = {}
        for n in ['string', 'rune', 'bool', 'int', 'location']:
            self.intrinsics[n] = model.IntrinsicType(n)

    def globalIsUsed(self, name):
        assert isinstance(name, basestring), name
        self.global_refs.add(name)

    def resolveSlot(self, name):
        assert isinstance(name, basestring), name
        if name in self.locals:
            return self.locals[name]
        if name in self.globals:
            self.globalIsUsed(name)
            return self.globals[name]

    def declareGlobal(self, name, t, loc):
        assert isinstance(name, basestring), name
        assert not isinstance(t, model.VoidType)
        if name in self.globals:
            self.status.error('Attempted to redefine "%s"' % name, loc)
        else:
            assert isinstance(t, model.Type), t
            self.globals[name] = t

    def setLocal(self, name, t):
        assert isinstance(name, basestring), name
        assert isinstance(t, model.Type), t
        assert not isinstance(t, model.VoidType), (self.scope_name, name)
        if name in self.locals:
            current = self.locals[name]
            if not can_hold(current, t):
                if can_hold(t, current):
                    self.locals[name] = t
                else:
                    raise Exception('Attempted to redefine "%s" (%r vs. %r)' % (name, current, t))
        else:
            self.locals[name] = t


class IndexGlobals(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.RuleDecl, model.ExternDecl)
    def visitCallableDecl(cls, node, semantic):
        name = node.name.text
        t = model.CallableType(name)
        semantic.declareGlobal(name, t, node.name.loc)
        if hasattr(node, 'attrs'):
            for attr in node.attrs:
                if attr.name.text == 'export':
                    # Mark exported decls as used.
                    semantic.globalIsUsed(name)

    @dispatch(model.StructDecl)
    def visitStructDecl(cls, node, semantic):
        name = node.name.text
        t = model.StructType(name, [])
        semantic.declareGlobal(name, t, node.name.loc)

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        name = node.name.text
        t = model.UnionType(name, [])
        semantic.declareGlobal(name, t, node.name.loc)


class ResolveType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.NameRef)
    def visitNameRef(cls, node, semantic):
        name = node.name.text
        if name == 'void':
            return semantic.void
        elif name in semantic.intrinsics:
            return semantic.intrinsics[name]
        elif name in semantic.globals:
            semantic.globalIsUsed(name)
            return semantic.globals[name]
        else:
            raise Exception('Unknown type "%s"' % name)

    @dispatch(model.ListRef)
    def visitListRef(cls, node, semantic):
        return cached_list_type(cls.visit(node.ref, semantic))


class CheckSignatures(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl)
    def visitStruct(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        for f in node.fields:
            nt.fields.append(model.Field(f.name.text, ResolveType.visit(f.t, semantic)))

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        nt.types = [ResolveType.visit(r, semantic) for r in node.refs]

    @dispatch(model.ExternDecl)
    def visitExternDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        nt.params = [ResolveType.visit(p.t, semantic) for p in node.params]
        nt.rt = ResolveType.visit(node.rt, semantic)

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        # TODO params
        nt.rt = ResolveType.visit(node.rt, semantic)


class CheckRules(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl, model.ExternDecl, model.UnionDecl)
    def visitNop(cls, node, semantic):
        pass

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        old_name = semantic.scope_name
        old_locals = semantic.locals
        semantic.scope_name = node.name.text
        semantic.locals = {}
        expected = ResolveType.visit(node.rt, semantic)
        actual = cls.visit(node.body, expected, semantic)
        if not can_hold(expected, actual):
            raise Exception('Expected return type of %r, got %r instead in %s.' % (expected, actual, semantic.scope_name))
        semantic.locals = old_locals
        semantic.scope_name = old_name

    @dispatch(model.Repeat)
    def visitRepeat(cls, node, expected_t, semantic):
        t = cls.visit(node.expr, expected_t, semantic)
        return t if node.min > 0 else semantic.void

    @dispatch(model.Choice)
    def visitChoice(cls, node, expected_t, semantic):
        types = [cls.visit(expr, expected_t, semantic) for expr in node.children]

        if not types:
            return semantic.void

        # Check if the types are idential.
        for t in types[1:]:
            if types[0] != t:
                break
        else:
            return types[0]

        if expected_t != semantic.void:
            # See if the expected type can hold them all.
            for t in types:
                if not can_hold(expected_t, t):
                    raise Exception('Cannot unify types: %r' % types)

        return expected_t

    @dispatch(model.Sequence)
    def visitSequence(cls, node, expected_t, semantic):
        t = semantic.void
        for i, expr in enumerate(node.children):
            expected_child = expected_t if i == len(node.children) - 1 else semantic.void
            t = cls.visit(expr, expected_child, semantic)
        return t

    @dispatch(model.Character)
    def visitCharacter(cls, node, expected_t, semantic):
        return semantic.intrinsics['rune']

    @dispatch(model.MatchValue)
    def visitMatchValue(cls, node, expected_t, semantic):
        return cls.visit(node.expr, expected_t, semantic)

    @dispatch(model.Slice)
    def visitSlice(cls, node, expected_t, semantic):
        cls.visit(node.expr, semantic.void, semantic)
        return semantic.intrinsics['string']

    @dispatch(model.Call)
    def visitCall(cls, node, expected_t, semantic):
        # TODO hint callable type?
        expr = cls.visit(node.expr, semantic.void, semantic)
        if isinstance(expr, model.CallableType):
            for i, arg in enumerate(node.args):
                if i < len(expr.params):
                    pt = expr.params[i]
                    t = cls.visit(arg, pt, semantic)
                    assert can_hold(pt, t), (pt, t)
                else:
                    cls.visit(arg, semantic.void, semantic)
            assert len(expr.params) == len(node.args), (node, expr.params)
            return expr.rt
        else:
            # TODO still evaluate args?
            raise Exception('Cannot call %r in %s' % (type(expr), semantic.scope_name))

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node, expected_t, semantic):
        st = ResolveType.visit(node.t, semantic)
        if isinstance(st, model.StructType):
            for i, arg in enumerate(node.args):
                if i < len(st.fields):
                    ft = st.fields[i].t
                    t = cls.visit(arg, ft, semantic)
                    assert can_hold(ft, t), (ft, t)
                else:
                    cls.visit(arg, semantic.void, semantic)
            assert len(st.fields) == len(node.args), (node, st.fields)
            return st
        else:
            raise Exception('Not a struct: %r in %s' % (st, semantic.scope_name))

    @dispatch(model.ListLiteral)
    def visitList(cls, node, expected_t, semantic):
        t = ResolveType.visit(node.t, semantic)
        for arg in node.args:
            at = cls.visit(arg, t, semantic)
            assert can_hold(t, at), (t, at, arg)
        return cached_list_type(t)

    @dispatch(model.Get)
    def visitGet(cls, node, expected_t, semantic):
        name = node.name.text
        t = semantic.resolveSlot(name)
        if t is None:
            raise Exception('Cannot resolve "%s" in %s' % (name, semantic.scope_name))
        return t

    @dispatch(model.Set)
    def visitSet(cls, node, expected_t, semantic):
        name = node.name.text
        t = cls.visit(node.expr, expected_t, semantic)
        if t == semantic.void:
            raise Exception('Cannot assign void to "%s" in %s' % (name, semantic.scope_name))
        semantic.setLocal(name, t)
        return t

    @dispatch(model.Append)
    def visitAppend(cls, node, expected_t, semantic):
        name = node.name.text
        lt = semantic.resolveSlot(name)
        if lt is None:
            raise Exception('Cannot resolve "%s" in %s' % (name, semantic.scope_name))
        # TODO assert is a local
        if not isinstance(lt, model.ListType):
            raise Exception('Cannot append to %r' % (lt,))
        t = cls.visit(node.expr, lt.t, semantic)
        if not can_hold(lt.t, t):
            raise Exception('Cannot append %r to %r' % (t, lt))
        return t

    @dispatch(model.Location)
    def visitStringLocation(cls, node, expected_t, semantic):
        return semantic.intrinsics['location']

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, expected_t, semantic):
        return semantic.intrinsics['string']

    @dispatch(model.RuneLiteral)
    def visitRuneLiteral(cls, node, expected_t, semantic):
        return semantic.intrinsics['rune']

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, expected_t, semantic):
        return semantic.intrinsics['int']

    @dispatch(model.BoolLiteral)
    def visitBoolLiteral(cls, node, expected_t, semantic):
        return semantic.intrinsics['bool']


class CheckUsed(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl, model.UnionDecl, model.ExternDecl, model.RuleDecl)
    def visitDecl(cls, node, semantic):
        name = node.name.text
        if name not in semantic.global_refs:
            semantic.status.error('Unused global "%s"' % name, node.name.loc)


def process(f, status):
    semantic = SemanticPass(status)
    IndexGlobals.visit(f, semantic)
    semantic.status.halt_if_errors()
    CheckSignatures.visit(f, semantic)
    semantic.status.halt_if_errors()
    CheckRules.visit(f, semantic)
    semantic.status.halt_if_errors()
    CheckUsed.visit(f, semantic)
    semantic.status.halt_if_errors()
