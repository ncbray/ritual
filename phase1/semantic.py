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
    def __init__(self):
        self.scope_name = 'global'
        self.globals = {}
        self.global_refs = set()
        self.locals = {}

        self.void = model.VoidType()
        self.intrinsics = {}
        for n in ['string', 'rune', 'bool', 'int']:
            self.intrinsics[n] = model.IntrinsicType(n)

    def resolveSlot(self, name):
        if name in self.locals:
            return self.locals[name]
        if name in self.globals:
            self.global_refs.add(name)
            return self.globals[name]

    def declareGlobal(self, name, t):
        assert not isinstance(t, model.VoidType)
        if name in self.globals:
            raise Exception('Attempted to redefine "%s"' % name)
        assert isinstance(t, model.Type), t
        self.globals[name] = t

    def setLocal(self, name, t):
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
        t = model.CallableType(node.name)
        semantic.declareGlobal(node.name, t)
        if hasattr(node, 'attrs'):
            for attr in node.attrs:
                if attr.name == 'export':
                    # Mark exported decls as used.
                    semantic.global_refs.add(node.name)

    @dispatch(model.StructDecl)
    def visitStructDecl(cls, node, semantic):
        t = model.StructType(node.name, [])
        semantic.declareGlobal(node.name, t)

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        t = model.UnionType(node.name, [])
        semantic.declareGlobal(node.name, t)


class ResolveType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.NameRef)
    def visitNameRef(cls, node, semantic):
        if node.name == 'void':
            return semantic.void
        elif node.name in semantic.intrinsics:
            return semantic.intrinsics[node.name]
        elif node.name in semantic.globals:
            semantic.global_refs.add(node.name)
            return semantic.globals[node.name]
        else:
            raise Exception('Unknown type "%s"' % node.name)
        return node.name

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
        nt = semantic.resolveSlot(node.name) # HACK
        for f in node.fields:
            nt.fields.append(model.Field(f.name, ResolveType.visit(f.t, semantic)))

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        nt = semantic.resolveSlot(node.name) # HACK
        nt.types = [ResolveType.visit(r, semantic) for r in node.refs]

    @dispatch(model.ExternDecl)
    def visitExternDecl(cls, node, semantic):
        nt = semantic.resolveSlot(node.name) # HACK
        nt.params = [ResolveType.visit(p, semantic) for p in node.params]
        nt.rt = ResolveType.visit(node.rt, semantic)

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        nt = semantic.resolveSlot(node.name) # HACK
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
        semantic.scope_name = node.name
        semantic.locals = {}
        t = cls.visit(node.body, semantic)
        semantic.locals = old_locals

    @dispatch(model.Repeat)
    def visitRepeat(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        return t if node.min > 0 else semantic.void

    @dispatch(model.Choice)
    def visitChoice(cls, node, semantic):
        if not node.children:
            return semantic.void
        types = [cls.visit(expr, semantic) for expr in node.children]

        # TODO this type inference is a little fiddly.
        # Pay attention to if the type is needed or not.
        for t in types[1:]:
            if types[0] != t:
                return semantic.void
        return types[0]

    @dispatch(model.Sequence)
    def visitSequence(cls, node, semantic):
        t = semantic.void
        for expr in node.children:
            t = cls.visit(expr, semantic)
        return t

    @dispatch(model.Character)
    def visitCharacter(cls, node, semantic):
        return semantic.intrinsics['rune']

    @dispatch(model.MatchValue)
    def visitMatchValue(cls, node, semantic):
        return cls.visit(node.expr, semantic)

    @dispatch(model.Slice)
    def visitSlice(cls, node, semantic):
        cls.visit(node.expr, semantic)
        return semantic.intrinsics['string']

    @dispatch(model.Call)
    def visitCall(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        if isinstance(t, model.StructType):
            # TODO check arg types.
            at = [cls.visit(arg, semantic) for arg in node.args]
            assert len(t.fields) == len(at), (node, t.fields, at)
            for f, at in zip(t.fields, at):
                assert can_hold(f.t, at), (f.t, at)
            return t
        elif isinstance(t, model.CallableType):
            assert t.rt, t
            at = [cls.visit(arg, semantic) for arg in node.args]
            assert len(t.params) == len(at), (node, t.params, at)
            for pt, at in zip(t.params, at):
                assert can_hold(pt, at), (pt, at)
            return t.rt
        else:
            raise Exception('Cannot call %r in %s' % (type(t), semantic.scope_name))


    @dispatch(model.List)
    def visitList(cls, node, semantic):
        t = ResolveType.visit(node.t, semantic)
        for arg in node.args:
            at = cls.visit(arg, semantic)
            assert t == at, (t, at, arg)
        return cached_list_type(t)

    @dispatch(model.Get)
    def visitGet(cls, node, semantic):
        t = semantic.resolveSlot(node.name)
        if t is None:
            raise Exception('Cannot resolve "%s" in %s' % (node.name, semantic.scope_name))
        return t

    @dispatch(model.Set)
    def visitSet(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        semantic.setLocal(node.name, t)
        return t

    @dispatch(model.Append)
    def visitAppend(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        # TODO assert is a local
        lt = semantic.resolveSlot(node.name)
        if lt is None:
            raise Exception('Cannot resolve "%s" in %s' % (node.name, semantic.scope_name))
        if not isinstance(lt, model.ListType):
            raise Exception('Cannot append to %r' % (lt,))
        if not can_hold(lt.t, t):
            raise Exception('Cannot append %r to %r' % (t, lt))
        return t

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, semantic):
        return semantic.intrinsics['string']

    @dispatch(model.RuneLiteral)
    def visitRuneLiteral(cls, node, semantic):
        return semantic.intrinsics['rune']

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, semantic):
        return semantic.intrinsics['int']

    @dispatch(model.BoolLiteral)
    def visitBoolLiteral(cls, node, semantic):
        return semantic.intrinsics['bool']


class CheckUsed(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl, model.UnionDecl, model.ExternDecl, model.RuleDecl)
    def visitDecl(cls, node, semantic):
        if node.name not in semantic.global_refs:
            raise Exception("Unused global: %s" % node.name)


def process(f):
    semantic = SemanticPass()
    IndexGlobals.visit(f, semantic)
    CheckSignatures.visit(f, semantic)
    CheckRules.visit(f, semantic)
    CheckUsed.visit(f, semantic)
