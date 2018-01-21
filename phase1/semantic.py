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

        self.globals = {}
        self.global_refs = set()

        self.scope_name = 'global'
        self.locals = {}
        self.local_locs = []
        self.local_refs = set()

        self.void = model.VoidType()
        self.intrinsics = {}
        for n in ['string', 'rune', 'bool', 'int', 'location']:
            self.intrinsics[n] = model.IntrinsicType(n)

    def globalIsUsed(self, name):
        assert isinstance(name, basestring), name
        self.global_refs.add(name)

    def resolveSlot(self, name, is_use):
        assert isinstance(name, basestring), name
        if name in self.locals:
            if is_use:
                self.local_refs.add(name)
            return self.locals[name]
        if name in self.globals:
            if is_use:
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

    def setLocal(self, name, t, loc):
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
            self.local_locs.append((name, loc))


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


class GetLoc(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.Get)
    def visitGet(cls, node):
        return node.name.loc

    @dispatch(model.Character, model.Slice, model.ListLiteral,
        model.StringLiteral, model.BoolLiteral, model.IntLiteral)
    def visitSimple(cls, node):
        return node.loc

    @dispatch(model.Repeat, model.Call)
    def visitHACK(cls, node):
        # TODO more accurate
        return cls.visit(node.expr)


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
        types = []
        for r in node.refs:
            t = ResolveType.visit(r, semantic)
            t.unions.append(nt)
            types.append(t)
        nt.types = types

    @dispatch(model.ExternDecl)
    def visitExternDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        nt.params = [ResolveType.visit(p.t, semantic) for p in node.params]
        nt.rt = ResolveType.visit(node.rt, semantic)

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        nt.params = [ResolveType.visit(p.t, semantic) for p in node.params]
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
        nt = semantic.globals[node.name.text] # HACK

        old_name = semantic.scope_name
        old_locals = semantic.locals
        semantic.scope_name = node.name.text
        semantic.locals = {}
        semantic.local_locs = []
        semantic.local_refs = set()
        expected = ResolveType.visit(node.rt, semantic)

        for p, t in zip(node.params, nt.params):
            semantic.setLocal(p.name.text, t, p.name.loc)

        actual = cls.visit(node.body, expected is not semantic.void, semantic)
        if expected is not semantic.void and not can_hold(expected, actual):
            semantic.status.error('Expected return type of %r, got %r instead.' % (expected, actual), node.name.loc)

        for name, loc in semantic.local_locs:
            if name not in semantic.local_refs:
                semantic.status.error('Unused local "%s"' % name, loc)

        semantic.locals = old_locals
        semantic.scope_name = old_name

    @dispatch(model.Repeat)
    def visitRepeat(cls, node, value_used, semantic):
        t = cls.visit(node.expr, value_used, semantic)
        # TODO nullable.
        return t if node.min > 0 else semantic.void

    @dispatch(model.Choice)
    def visitChoice(cls, node, value_used, semantic):
        types = [cls.visit(expr, value_used, semantic) for expr in node.children]

        if not types:
            return semantic.void

        # Try to unify the types.
        guess = types[0]
        for t in types[1:]:
            # Identical types?
            if t is guess:
                continue
            # The current guess can hold the new type.
            if can_hold(guess, t):
                continue
            # The new type can hold the current guess.
            if can_hold(t, guess):
                guess = t
                continue
            # If the types have exactly one union in common, chose it.
            if isinstance(guess, model.StructType) and isinstance(t, model.StructType):
                common = set(guess.unions).intersection(set(t.unions))
                if len(common) == 1:
                    guess = common.pop()
                    continue
            # Failed to unify.
            break
        else:
            return guess

        if value_used:
            semantic.status.error('Cannot unify types: %r' % types)
        return semantic.void

    @dispatch(model.Sequence)
    def visitSequence(cls, node, value_used, semantic):
        t = semantic.void
        for i, expr in enumerate(node.children):
            child_used = value_used and i == len(node.children) - 1
            t = cls.visit(expr, child_used, semantic)
        return t

    @dispatch(model.Character)
    def visitCharacter(cls, node, value_used, semantic):
        return semantic.intrinsics['rune']

    @dispatch(model.MatchValue)
    def visitMatchValue(cls, node, value_used, semantic):
        return cls.visit(node.expr, True, semantic)

    @dispatch(model.Slice)
    def visitSlice(cls, node, value_used, semantic):
        cls.visit(node.expr, False, semantic)
        if not value_used:
            semantic.status.error('Unused slice.', node.loc)
        return semantic.intrinsics['string']

    @dispatch(model.Lookahead)
    def visitLookahead(cls, node, value_used, semantic):
        t = cls.visit(node.expr, value_used and not node.invert, semantic)
        if node.invert:
            return semantic.void
        else:
            return t

    @dispatch(model.Call)
    def visitCall(cls, node, value_used, semantic):
        expr = cls.visit(node.expr, semantic.void, semantic)
        args = [cls.visit(arg, True, semantic) for arg in node.args]

        if not isinstance(expr, model.CallableType):
            # TODO still evaluate args?
            semantic.status.error('Cannot call %r in %s' % (type(expr), semantic.scope_name))
            return semantic.void

        if len(args) != len(expr.params):
            semantic.status.error('Expected %d arguments, got %d instead.' % (len(expr.params), len(args)), GetLoc.visit(node))
        else:
            for pt, at, a in zip(expr.params, args, node.args):
                if not can_hold(pt, at):
                    semantic.status.error('Expected %r, got %r instead.' % (pt, at), GetLoc.visit(a))
        return expr.rt

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
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
    def visitListLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        t = ResolveType.visit(node.t, semantic)
        for arg in node.args:
            at = cls.visit(arg, t, semantic)
            assert can_hold(t, at), (t, at, arg)
        return cached_list_type(t)

    @dispatch(model.Get)
    def visitGet(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused get.', node.loc)
        name = node.name.text
        t = semantic.resolveSlot(name, True)
        if t is None:
            raise Exception('Cannot resolve "%s" in %s' % (name, semantic.scope_name))
        return t

    @dispatch(model.Set)
    def visitSet(cls, node, value_used, semantic):
        name = node.name.text
        t = cls.visit(node.expr, True, semantic)
        if t == semantic.void:
            raise Exception('Cannot assign void to "%s" in %s' % (name, semantic.scope_name))
        semantic.setLocal(name, t, node.name.loc)
        return t

    @dispatch(model.Append)
    def visitAppend(cls, node, value_used, semantic):
        name = node.name.text
        lt = semantic.resolveSlot(name, False)
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
    def visitLocation(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused location.', node.loc)
        return semantic.intrinsics['location']

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return semantic.intrinsics['string']

    @dispatch(model.RuneLiteral)
    def visitRuneLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return semantic.intrinsics['rune']

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return semantic.intrinsics['int']

    @dispatch(model.BoolLiteral)
    def visitBoolLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
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


class Simplify(object):
    __metaclass__ = TypeDispatcher

    @dispatch(list)
    def visitList(cls, node):
        for child in node:
            cls.visit(child)

    @dispatch(model.Token, model.Param, model.NameRef, model.ListRef, model.Get,
        model.Character, bool, str, unicode, int, model.Attribute,
        model.StringLiteral, model.BoolLiteral, model.IntLiteral,
        model.RuneLiteral, model.Location)
    def visitLeaf(cls, node):
        pass

    @dispatch(model.Sequence)
    def visitSequence(cls, node):
        out = []
        for child in node.children:
            cls.visit(child)
            if isinstance(child, model.Sequence):
                out.extend(child.children)
            else:
                out.append(child)
        assert len(out) > 1, out
        node.children = out

    @dispatch(model.Choice)
    def visitChoice(cls, node):
        out = []
        for child in node.children:
            cls.visit(child)
            if isinstance(child, model.Choice):
                out.extend(child.children)
            else:
                out.append(child)
        assert len(out) > 1, out
        node.children = out

    @dispatch(model.File, model.StructDecl, model.UnionDecl, model.ExternDecl,
        model.RuleDecl, model.MatchValue, model.Set, model.Append,
        model.Lookahead, model.Call, model.StructLiteral, model.ListLiteral,
        model.Repeat, model.Slice, model.FieldDecl)
    def visitNode(cls, node):
        for slot in node.__slots__:
            cls.visit(getattr(node, slot))


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
    Simplify.visit(f)
    semantic.status.halt_if_errors()
