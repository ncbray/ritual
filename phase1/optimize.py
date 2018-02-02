from base import TypeDispatcher, dispatch
import model


MAX = 0xffffff


def canonicalize_ranges(ranges):
    if not ranges:
        return ()
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
        self.status = status


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
        return node

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, opt):
        node.body = cls.visit(node.body, opt)

    @dispatch(model.StructDecl, model.UnionDecl, model.ExternDecl)
    def visitStructDecl(cls, node, opt):
        pass

    @dispatch(model.File)
    def visitFile(cls, node, opt):
        for decl in node.decls:
            cls.visit(decl, opt)


def process(f, status):
    opt = OptimizationPass(status)
    DoOpt.visit(f, opt)