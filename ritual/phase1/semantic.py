from ritual.base import TypeDispatcher, dispatch
from . import model


def cached_list_type(node, t, semantic):
    if isinstance(t, model.PoisonType):
        return t
    if hasattr(t, 'list_cache'):
        if t.list_cache is None:
            t.list_cache = model.ListType(t)
        return t.list_cache
    else:
        semantic.status.error('Cannot create a list of %r.' % (t), GetLoc.visit(node))
        return semantic.poison



def can_hold(general, specific):
    if general is specific:
        return True
    elif isinstance(general, model.UnionType):
        for t in general.types:
            if can_hold(t, specific):
                return True
        return False
    elif isinstance(general, model.PoisonType):
        return True
    elif isinstance(specific, model.PoisonType):
        return True
    return False


class LocalSlot(object):
    def __init__(self, t):
        self.t = t


class SemanticPass(object):
    def __init__(self, status):
        self.status = status

        self.globals = {}
        self.global_refs = set()

        self.locals = {}
        self.local_refs = set()

        self.void = model.VoidType()
        self.poison = model.PoisonType()
        self.intrinsics = {}
        for n in ['string', 'rune', 'bool', 'int', 'location']:
            self.intrinsics[n] = model.IntrinsicType(n)

        self.current_rule = None

    def globalIsUsed(self, name):
        assert isinstance(name, str), name
        self.global_refs.add(name)

    def resolveSlot(self, name, is_use):
        assert isinstance(name, str), name
        if name in self.locals:
            if is_use:
                self.local_refs.add(name)
            return self.locals[name]
        if name in self.globals:
            if is_use:
                self.globalIsUsed(name)
            return self.globals[name]

    def declareGlobal(self, name, t, loc):
        assert isinstance(name, str), name
        assert not isinstance(t, model.VoidType)
        if name in self.globals:
            self.status.error('Attempted to redefine "%s"' % name, loc)
            self.globals[name] = self.poison
        else:
            assert isinstance(t, model.Type), t
            self.globals[name] = t

    def setLocal(self, name, t, loc):
        assert isinstance(name, str), name
        assert isinstance(t, model.Type), t
        assert not isinstance(t, model.VoidType), name
        if name in self.locals:
            lcl = self.locals[name]
            current = lcl.t
            if not can_hold(current, t):
                if can_hold(t, current):
                    lcl.t = t
                else:
                    self.status.error('Attempted to redefine "%s" (%r vs. %r)' % (name, current, t), loc)
                    lcl.t = self.poison
        else:
            lcl = model.Local(loc, name, t)
            self.locals[name] = lcl
        return lcl


class IndexGlobals(object, metaclass=TypeDispatcher):

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.ExternDecl)
    def visitExternDecl(cls, node, semantic):
        name = node.name.text
        t = model.ExternType(name)
        semantic.declareGlobal(name, t, node.name.loc)

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        name = node.name.text
        t = model.RuleType(name)
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


class GetLoc(object, metaclass=TypeDispatcher):

    @dispatch(model.ListRef)
    def visitListRef(cls, node):
        # TODO more accurate
        return cls.visit(node.ref)

    @dispatch(model.Get, model.NameRef)
    def visitGet(cls, node):
        return node.name.loc

    @dispatch(model.GetLocal, model.DirectCall, model.DirectRef)
    def visitEmbedded(cls, node):
        return node.loc

    @dispatch(model.Sequence, model.Choice)
    def visitSequence(cls, node):
        return GetLoc.visit(node.children[0])


    @dispatch(model.Character, model.Slice, model.ListLiteral, model.StructLiteral,
        model.StringLiteral, model.BoolLiteral, model.IntLiteral)
    def visitSimple(cls, node):
        return node.loc

    @dispatch(model.Repeat, model.Call)
    def visitHACK(cls, node):
        # TODO more accurate
        return cls.visit(node.expr)


class ResolveType(object, metaclass=TypeDispatcher):

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
            semantic.status.error('Unknown type "%s"' % name, node.name.loc)
            return semantic.poison

    @dispatch(model.ListRef)
    def visitListRef(cls, node, semantic):
        return cached_list_type(node.ref, cls.visit(node.ref, semantic), semantic)

    @dispatch(model.DirectRef)
    def visitDirectRef(cls, node, semantic):
        return node.t


class CheckSignatures(object, metaclass=TypeDispatcher):

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl)
    def visitStruct(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        for f in node.fields:
            ft =  ResolveType.visit(f.t, semantic)
            nt.fields.append(model.Field(f.name.text, ft))
            f.t = model.DirectRef(GetLoc.visit(f.t), ft)

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK
        types = []
        for i, r in enumerate(node.refs):
            t = ResolveType.visit(r, semantic)
            t.unions.append(nt)
            types.append(t)
            node.refs[i] = model.DirectRef(GetLoc.visit(r), t)
        nt.types = types

    @dispatch(model.ExternDecl)
    def visitExternDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK

        params = []
        for p in node.params:
            t = ResolveType.visit(p.t, semantic)
            p.t = model.DirectRef(GetLoc.visit(p.t), t)
            params.append(t)
        nt.params = params

        rt = ResolveType.visit(node.rt, semantic)
        node.rt = model.DirectRef(GetLoc.visit(node.rt), rt)
        nt.rt = rt

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        nt = semantic.globals[node.name.text] # HACK

        params = []
        for p in node.params:
            t = ResolveType.visit(p.t, semantic)
            p.t = model.DirectRef(GetLoc.visit(p.t), t)
            params.append(t)
        nt.params = params

        rt = ResolveType.visit(node.rt, semantic)
        node.rt = model.DirectRef(GetLoc.visit(node.rt), rt)
        nt.rt = rt


class CheckRules(object, metaclass=TypeDispatcher):

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

        old_locals = semantic.locals
        semantic.locals = {}
        semantic.local_refs = set()
        semantic.current_rule = nt

        expected = ResolveType.visit(node.rt, semantic)

        for p, t in zip(node.params, nt.params):
            semantic.setLocal(p.name.text, t, p.name.loc)

        node.body, actual = cls.visit(node.body, expected is not semantic.void, semantic)
        if expected is not semantic.void and not can_hold(expected, actual):
            semantic.status.error('Expected return type of %r, got %r instead.' % (expected, actual), node.name.loc)

        for lcl in semantic.current_rule.locals:
            if lcl.name not in semantic.local_refs:
                semantic.status.error('Unused local "%s"' % lcl.name, lcl.loc)

        semantic.current_rule = None
        semantic.locals = old_locals

    @dispatch(model.Repeat)
    def visitRepeat(cls, node, value_used, semantic):
        node.expr, t = cls.visit(node.expr, value_used, semantic)
        # TODO nullable.
        return node, t if node.min > 0 else semantic.void

    @classmethod
    def visitArgs(cls, args, semantic):
        children = []
        types = []
        for expr in args:
            expr, t = cls.visit(expr, True, semantic)
            children.append(expr)
            types.append(t)
        return children, types

    @dispatch(model.Choice)
    def visitChoice(cls, node, value_used, semantic):
        node.children, types = cls.visitArgs(node.children, semantic)

        if len(node.children) == 1:
            node = node.children[0]

        if not types:
            return node, semantic.void

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
            return node, guess

        if value_used:
            semantic.status.error('Cannot unify types: %r' % types)
        return node, semantic.poison

    @dispatch(model.Sequence)
    def visitSequence(cls, node, value_used, semantic):
        t = semantic.void
        children = []
        for i, expr in enumerate(node.children):
            child_used = value_used and i == len(node.children) - 1
            expr, t = cls.visit(expr, child_used, semantic)
            children.append(expr)
        node.children = children
        if len(node.children) == 1:
            node = node.children[0]
        return node, t

    @dispatch(model.Character)
    def visitCharacter(cls, node, value_used, semantic):
        return node, semantic.intrinsics['rune']

    @dispatch(model.MatchValue)
    def visitMatchValue(cls, node, value_used, semantic):
        node.expr, t = cls.visit(node.expr, True, semantic)
        return node, t

    @dispatch(model.Slice)
    def visitSlice(cls, node, value_used, semantic):
        node.expr, _ = cls.visit(node.expr, False, semantic)
        if not value_used:
            semantic.status.error('Unused slice.', node.loc)
        return node, semantic.intrinsics['string']

    @dispatch(model.Lookahead)
    def visitLookahead(cls, node, value_used, semantic):
        node.expr, t = cls.visit(node.expr, value_used and not node.invert, semantic)
        if node.invert:
            t = semantic.void
        return node, t

    @dispatch(model.Call)
    def visitCall(cls, node, value_used, semantic):
        node.expr, expr = cls.visit(node.expr, semantic.void, semantic)
        node.args, args = cls.visitArgs(node.args, semantic)

        if isinstance(expr, model.CallableType):
            node = model.DirectCall(GetLoc.visit(node.expr), expr, node.args)
        else:
            if not isinstance(expr, model.PoisonType):
                semantic.status.error('Cannot call %r' % (expr,), node.loc)
            return node, semantic.poison

        if len(args) != len(expr.params):
            semantic.status.error('Expected %d arguments, got %d instead.' % (len(expr.params), len(args)), GetLoc.visit(node))
        else:
            for pt, at, a in zip(expr.params, args, node.args):
                if not can_hold(pt, at):
                    semantic.status.error('Expected %r, got %r instead.' % (pt, at), GetLoc.visit(a))
        return node, expr.rt

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        st = ResolveType.visit(node.t, semantic)
        node.t = model.DirectRef(GetLoc.visit(node.t), st)
        node.args, args = cls.visitArgs(node.args, semantic)

        if isinstance(st, model.PoisonType):
            return node, st

        if not isinstance(st, model.StructType):
            semantic.status.error('Not a struct', GetLoc.visit(node.t))
            return node, semantic.poison

        if len(args) != len(st.fields):
            semantic.status.error('Expected %d arguments, got %d instead.' % (len(st.fields), len(args)), GetLoc.visit(node))
        else:
            for f, at, a in zip(st.fields, args, node.args):
                if not can_hold(f.t, at):
                    semantic.status.error('Expected %r, got %r instead.' % (f.t, at), GetLoc.visit(a))
        return node, st

    @dispatch(model.ListLiteral)
    def visitListLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        t = ResolveType.visit(node.t, semantic)
        node.t = model.DirectRef(GetLoc.visit(node.t), t)

        node.args, args = cls.visitArgs(node.args, semantic)
        lt = cached_list_type(node.t, t, semantic)
        if isinstance(lt, model.ListType):
            for arg, at in zip(node.args, args):
                if not can_hold(t, at):
                    semantic.status.error('Expected %r, got %r instead.' % (t, at), GetLoc.visit(arg))
        return node, lt

    @dispatch(model.Get)
    def visitGet(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused get.', node.loc)
        name = node.name.text
        t = semantic.resolveSlot(name, True)
        if t is None:
            semantic.status.error('Cannot resolve "%s"' % (name,), node.name.loc)
            t = semantic.poison
        if isinstance(t, model.Local):
            node = model.GetLocal(node.name.loc, t)
            t = t.t
        return node, t

    @dispatch(model.Set)
    def visitSet(cls, node, value_used, semantic):
        name = node.name.text
        node.expr, t = cls.visit(node.expr, True, semantic)
        if t == semantic.void:
            semantic.status.error('Cannot assign void to "%s"' % (name,), node.name.loc)
            t = semantic.poison
        lcl = semantic.setLocal(name, t, node.name.loc)
        node = model.SetLocal(node.expr, lcl)
        return node, t

    @dispatch(model.Append)
    def visitAppend(cls, node, value_used, semantic):
        name = node.name.text
        loc = node.name.loc
        lt = semantic.resolveSlot(name, False)
        if lt is None:
            semantic.status.error('Cannot resolve "%s"' % (name,), oc)

        node.expr, t = cls.visit(node.expr, True, semantic)
        if isinstance(lt, model.Local):
            node = model.AppendLocal(node.expr, lt)
            lt = lt.t
        elif lt is not semantic.poison:
            semantic.status.error('"%s" is not a local' % (name,), loc)

        if lt is semantic.poison:
            pass
        elif not isinstance(lt, model.ListType):
            semantic.status.error('Cannot append to "%r"' % (lt,), loc)
        elif not can_hold(lt.t, t):
            semantic.status.error('Cannot append %r to %r' % (t, lt), loc)
        return node, t

    @dispatch(model.Location)
    def visitLocation(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused location.', node.loc)
        return node, semantic.intrinsics['location']

    @dispatch(model.StringLiteral)
    def visitStringLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return node, semantic.intrinsics['string']

    @dispatch(model.RuneLiteral)
    def visitRuneLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return node, semantic.intrinsics['rune']

    @dispatch(model.IntLiteral)
    def visitIntLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return node, semantic.intrinsics['int']

    @dispatch(model.BoolLiteral)
    def visitBoolLiteral(cls, node, value_used, semantic):
        if not value_used:
            semantic.status.error('Unused literal.', node.loc)
        return node, semantic.intrinsics['bool']


class CheckUsed(object, metaclass=TypeDispatcher):

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl, model.UnionDecl, model.ExternDecl, model.RuleDecl)
    def visitDecl(cls, node, semantic):
        name = node.name.text
        if name not in semantic.global_refs:
            semantic.status.error('Unused global "%s"' % name, node.name.loc)


class Simplify(object, metaclass=TypeDispatcher):

    @dispatch(list)
    def visitList(cls, node):
        for child in node:
            cls.visit(child)

    @dispatch(model.Token, model.Param, model.NameRef, model.ListRef, model.DirectRef,
        model.GetLocal, model.Character, bool, str, int, model.Local,
        model.Attribute, model.StringLiteral, model.BoolLiteral, model.IntLiteral,
        model.RuneLiteral, model.Location, model.RuleType, model.ExternType)
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
        model.RuleDecl, model.MatchValue, model.SetLocal, model.AppendLocal,
        model.Lookahead, model.DirectCall, model.StructLiteral, model.ListLiteral,
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
