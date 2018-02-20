from ritual.base import TypeDispatcher, dispatch
import model


MAX = 0xffffff
ALL = ((0, MAX),)
NONE = ()


def ranges_intersect(a, b):
    return intersect_ranges(a, b) != NONE


def intersect_ranges(a, b):
    return invert_ranges(union_ranges(invert_ranges(a), invert_ranges(b)))


def union_ranges(a, b):
    if not a:
        return b
    elif not b:
        return a
    elif a == ALL or b == ALL:
        return ALL

    l = list(a + b)
    l.sort(key=lambda r: r[0])
    out = []
    a = l[0][0]
    b = l[0][1]
    for i in range(1, len(l)):
        c, d = l[i]
        if b >= c - 1:
            # Merge
            b = max(b, d)
        else:
            # Start new range
            out.append((a, b))
            a = c
            b = d
    out.append((a, b))
    return tuple(out)

def canonicalize_ranges(ranges):
    if not ranges:
        return NONE
    ranges = list(ranges)
    ranges.sort(key=lambda r: r.lower)
    a = ord(ranges[0].lower)
    b = ord(ranges[0].upper)
    out = []
    for i in range(1, len(ranges)):
        r = ranges[i]
        c = ord(r.lower)
        d = ord(r.upper)
        if b >= c - 1:
            # Merge
            b = max(b, d)
        else:
            # Start new range
            out.append((a, b))
            a = c
            b = d
    out.append((a, b))
    return tuple(out)


def invert_ranges(ranges):
    if not ranges:
        return ALL
    out = []
    prev = 0
    for r in ranges:
        next = r[0] - 1
        if next >= prev:
            out.append((prev, next))
        prev = r[1] + 1
    if prev <= MAX:
        out.append((prev, MAX))
    return tuple(out)


def model_to_canonical(ranges, inv):
    ranges = canonicalize_ranges(ranges)
    if inv:
        ranges = invert_ranges(ranges)
    return ranges


def canonical_to_model(ranges):
    invert = False
    if ranges and ranges[-1][1] == MAX:
        ranges = invert_ranges(ranges)
        invert = True
    return [model.Range(unichr(r[0]), unichr(r[1])) for r in ranges], invert


class OptimizationPass(object):
    def __init__(self, status):
        self.prefix_cache = {}
        self.rules = {}
        self.status = status


NO = 0
MAY = 1
MUST = 2


def merge_two(ra, ma, rb, mb):
    assert ma != MUST
    if ma == NO:
        return rb, mb
    elif mb == NO:
        return ra, ma
    assert ma == MAY
    return union_ranges(ra, rb), MUST if mb == MUST else MAY


def merge_sequence(cls, s, opt):
    accum = NONE
    m = NO
    for e in s:
        ranges, mode = cls.cachedVisit(e, opt)
        accum, m = merge_two(accum, m, ranges, mode)
        if m == MUST:
            return accum, m
    return accum, m


class GetPossiblePrefix(object):
    __metaclass__ = TypeDispatcher

    @classmethod
    def cachedVisit(cls, node, opt):
        if node not in opt.prefix_cache:
            # Pesimism in the face of recusion
            # TODO this is left recursion and it should be an error?
            opt.prefix_cache[node] = (ALL, MAY)
            opt.prefix_cache[node] = cls.visit(node, opt)
        return opt.prefix_cache[node]

    @dispatch(model.GetLocal, model.BoolLiteral, model.IntLiteral, model.StringLiteral, model.RuneLiteral, model.Location)
    def visitTerminal(cls, node, opt):
        return NONE, NO

    @dispatch(model.Character)
    def visitCharacter(cls, node, opt):
        return model_to_canonical(node.ranges, node.invert), MUST

    @dispatch(model.MatchValue)
    def visitMatchValue(cls, node, opt):
        assert isinstance(node.expr, model.StringLiteral), node
        value = node.expr.value
        if not value:
            return NONE, NO
        c = ord(value[0])
        return ((c, c),), MUST

    @dispatch(model.ListLiteral)
    def visitListLiteral(cls, node, opt):
        return merge_sequence(cls, node.args, opt)

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node, opt):
        return merge_sequence(cls, node.args, opt)

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node, opt):
        ranges, mode = merge_sequence(cls, node.args, opt)
        if mode == MUST or isinstance(node.func, model.ExternType):
            return ranges, mode

        # HACK
        name = node.func.name
        rule = opt.rules[name]
        call_ranges, call_mode = cls.cachedVisit(rule.body, opt)
        return merge_two(ranges, mode, call_ranges, call_mode)

    @dispatch(model.Slice, model.SetLocal, model.AppendLocal)
    def visitSimpleWrapper(cls, node, opt):
        return cls.cachedVisit(node.expr, opt)

    @dispatch(model.Repeat)
    def visitRepeat(cls, node, opt):
        ranges, mode = cls.cachedVisit(node.expr, opt)
        if mode == MUST and node.min == 0:
            mode = MAY
        return ranges, mode

    @dispatch(model.Sequence)
    def visitSequence(cls, node, opt):
        return merge_sequence(cls, node.children, opt)

    @dispatch(model.Choice)
    def visitChoice(cls, node, opt):
        accum = NONE
        m = MUST
        for child in node.children:
            ranges, mode = cls.cachedVisit(child, opt)
            if mode != NO:
                accum = union_ranges(accum, ranges)
            if mode != MUST:
                m = MAY
        return accum, m


class DoOpt(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.Character)
    def visitCharacter(cls, node, opt):
        # Canonicalize and simplify where possible.
        ranges = model_to_canonical(node.ranges, node.invert)
        node.ranges, node.invert = canonical_to_model(ranges)
        return node

    @dispatch(model.MatchValue)
    def visitMatchValue(cls, node, opt):
        node.expr = cls.visit(node.expr, opt)
        if isinstance(node.expr, model.StringLiteral) and len(node.expr.value) == 1:
            # Convert single-character string into character match.
            c = node.expr.value[0]
            return model.Character(node.loc, [model.Range(c, c)], False)
        return node

    @dispatch(model.GetLocal, model.StringLiteral, model.IntLiteral, model.BoolLiteral, model.RuneLiteral, model.Location)
    def visitLeaf(cls, node, opt):
        return node

    @dispatch(model.Lookahead, model.SetLocal, model.AppendLocal, model.Slice, model.Repeat)
    def visitSimpleExpr(cls, node, opt):
        node.expr = cls.visit(node.expr, opt)
        return node

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node, opt):
        for i, arg in enumerate(node.args):
            node.args[i] = cls.visit(arg, opt)
        return node

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node, opt):
        for i, arg in enumerate(node.args):
            node.args[i] = cls.visit(arg, opt)
        return node

    @dispatch(model.ListLiteral)
    def visitListLiteral(cls, node, opt):
        for i, arg in enumerate(node.args):
            node.args[i] = cls.visit(arg, opt)
        return node

    @dispatch(model.Sequence)
    def visitSequence(cls, node, opt):
        children = []
        for child in node.children:
            child = cls.visit(child, opt)
            if isinstance(child, model.Sequence):
                children.extend(child.children)
            else:
                children.append(child)
        if len(children) == 1:
            return children[0]
        node.children = children
        return node

    @dispatch(model.Choice)
    def visitChoice(cls, node, opt):
        children = []
        for child in node.children:
            child = cls.visit(child, opt)
            if isinstance(child, model.Choice):
                children.extend(child.children)
            else:
                children.append(child)
        if len(children) == 1:
            return children[0]
        node.children = children

        # Are the choices disjoint?
        accum = NONE
        child_prefixes = []
        for child in node.children:
            ranges, mode = GetPossiblePrefix.cachedVisit(child, opt)
            if mode != MUST:
                break
            if ranges_intersect(accum, ranges):
                break
            accum = union_ranges(accum, ranges)
            child_prefixes.append(ranges)
        else:
            # TODO optimize disjoint ranges.
            pass

        return node

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, opt):
        node.body = cls.visit(node.body, opt)

    @dispatch(model.StructDecl, model.UnionDecl, model.ExternDecl)
    def visitStructDecl(cls, node, opt):
        pass

    @dispatch(model.File)
    def visitFile(cls, node, opt):
        # HACK
        for decl in node.decls:
            opt.rules[decl.name.text] = decl

        for decl in node.decls:
            cls.visit(decl, opt)


def process(f, status):
    opt = OptimizationPass(status)
    DoOpt.visit(f, opt)