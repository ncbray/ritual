from base import TypeDispatcher, dispatch
import interpreter
import model


class LocalSlot(object):
    def __init__(self, t):
        self.t = t


class SemanticPass(object):
    def __init__(self):
        self.scope_name = 'global'
        self.globals = {}
        self.global_refs = set()
        self.locals = {}

    def resolveSlot(self, name):
        if name in self.locals:
            return self.locals[name]
        if name in self.globals:
            self.global_refs.add(name)
            return self.globals[name]


class IndexGlobals(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.RuleDecl, model.ExternDecl, model.StructDecl, model.UnionDecl)
    def visitNamedDecl(cls, node, semantic):
        if node.name in semantic.globals:
            raise Exception('Attempted to redefine "%s"' % node.name)
        semantic.globals[node.name] = node
        if hasattr(node, 'attrs'):
            for attr in node.attrs:
                if attr.name == 'export':
                    # Mark exported decls as used.
                    semantic.global_refs.add(node.name)


class ResolveType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.NameRef)
    def visitNameRef(cls, node, semantic):
        if node.name in set(['string', 'int', 'rune', 'void', 'bool']):
            return node.name
        elif node.name in semantic.globals:
            semantic.global_refs.add(node.name)
            t = semantic.globals[node.name]
            assert isinstance(t, (model.StructDecl, model.UnionDecl)), t
        else:
            raise Exception('Unknown type "%s"' % node.name)

    @dispatch(model.ListRef)
    def visitListRef(cls, node, semantic):
        cls.visit(node.ref, semantic)


class CheckSignatures(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl)
    def visitStruct(cls, node, semantic):
        for f in node.fields:
            ResolveType.visit(f.t, semantic)

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        for t in node.refs:
            ResolveType.visit(t, semantic)


    @dispatch(model.ExternDecl)
    def visitExternDecl(cls, node, semantic):
        for p in node.params:
            ResolveType.visit(p, semantic)
        ResolveType.visit(node.rt, semantic)

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        ResolveType.visit(node.rt, semantic)


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

    @dispatch(interpreter.Repeat)
    def visitRepeat(cls, node, semantic):
        cls.visit(node.expr, semantic)
        return 'void'

    @dispatch(interpreter.Choice)
    def visitChoice(cls, node, semantic):
        for expr in node.children:
            cls.visit(expr, semantic)
        return 'void'

    @dispatch(interpreter.Sequence)
    def visitSequence(cls, node, semantic):
        t = 'void'
        for expr in node.children:
            t = cls.visit(expr, semantic)
        return t

    @dispatch(interpreter.Character)
    def visitCharacter(cls, node, semantic):
        return 'rune'

    @dispatch(interpreter.MatchValue)
    def visitMatchValue(cls, node, semantic):
        return 'string' # HACK

    @dispatch(interpreter.Slice)
    def visitSlice(cls, node, semantic):
        cls.visit(node.expr, semantic)
        return 'string'

    @dispatch(interpreter.Call)
    def visitCall(cls, node, semantic):
        expr = cls.visit(node.expr, semantic)
        #if not isinstance(expr, (model.RuleDecl, model.ExternDecl, model.StructDecl)):
        #    raise Exception('Cannot call %r in %s' % (type(expr), semantic.scope_name))
        for arg in node.args:
            cls.visit(arg, semantic)
        return '?'

    @dispatch(interpreter.List)
    def visitList(cls, node, semantic):
        for arg in node.args:
            cls.visit(arg, semantic)
        return '[]?'

    @dispatch(interpreter.Get)
    def visitGet(cls, node, semantic):
        slot = semantic.resolveSlot(node.name)
        if slot is None:
            raise Exception('Cannot resolve "%s" in %s' % (node.name, semantic.scope_name))

    @dispatch(interpreter.Set)
    def visitSet(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        semantic.locals[node.name] = LocalSlot(t)
        return t

    @dispatch(interpreter.Append)
    def visitAppend(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        slot = semantic.resolveSlot(node.name)
        if slot is None:
            raise Exception('Cannot resolve "%s" in %s' % (node.name, semantic.scope_name))
        return 'void'

    @dispatch(interpreter.Literal)
    def visitLiteral(cls, node, semantic):
        return '?'


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
