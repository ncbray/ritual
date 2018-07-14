import io

from ritual.base import TypeDispatcher, dispatch
import ritual.interpreter.location

from . import generate_python
from . import model
from . import parser


class SemanticPass(object):
    def __init__(self, status):
        self.status = status
        self.globals = model.StrictNamespace()

    def defineGlobal(self, tok, value):
        self.globals.define(tok, value, self.status)


class IndexGlobals(object, metaclass=TypeDispatcher):

    @dispatch(parser.StructDecl)
    def visitStructDecl(cls, node, semantic):
        s = model.Struct(node.name.text, model.StrictNamespace())
        semantic.defineGlobal(node.name, s)

    @dispatch(parser.EdgeDecl)
    def visitEdgeDecl(cls, node, semantic):
        e = model.Edge(node.name.text)
        semantic.defineGlobal(node.name, e)

    @dispatch(parser.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)


class ResolveTypes(object, metaclass=TypeDispatcher):

    @dispatch(parser.TypeRef)
    def visitTypeRef(cls, node, semantic):
        t = semantic.globals.index.get(node.name.text)
        if t is None:
            semantic.status.error('unknown type "%s"' % node.name.text, node.name.loc)
            return None
        if not isinstance(t, model.Struct):
            semantic.status.error('"%s" is not a struct' % node.name.text, node.name.loc)
            return None
        return t

    @dispatch(parser.StructDecl)
    def visitStructDecl(cls, node, semantic):
        s = semantic.globals.index[node.name.text]
        return s

    @dispatch(parser.ScalarPortDecl)
    def visitScalarPortDecl(cls, node, e, src, owns, semantic):
        t = cls.visit(node.t, semantic)
        if t is None:
            return None
        names = [name.text for name in node.names]
        p = model.ScalarPort(names=names, t=t, edge=e, src=src, owner=owns)
        for name in node.names:
            t.ns.define(name, p, semantic.status)
        t.ports.append(p)
        return p

    @dispatch(parser.IndexedPortDecl)
    def visitIndexedPortDecl(cls, node, e, src, owns, semantic):
        assert owns, node
        t = cls.visit(node.t, semantic)
        if t is None:
            return None
        p = model.IndexedPort(name=node.name.text, t=t, edge=e, src=src, owner=owns)
        t.ns.define(node.name, p, semantic.status)
        t.ports.append(p)
        return p

    @dispatch(parser.BagPortDecl)
    def visitBagPortDecl(cls, node, e, src, owns, semantic):
        assert not owns, node
        t = cls.visit(node.t, semantic)
        if t is None:
            return None
        p = model.BagPort(name=node.name.text, t=t, edge=e, src=src)
        t.ns.define(node.name, p, semantic.status)
        t.ports.append(p)
        return p

    @dispatch(parser.EdgeDecl)
    def visitEdgeDecl(cls, node, semantic):
        e = semantic.globals.index[node.name.text]
        src_owns = False
        dst_owns = False
        if isinstance(node.src, parser.BagPortDecl) or isinstance(node.dst, parser.IndexedPortDecl):
            dst_owns = True
        if isinstance(node.dst, parser.BagPortDecl) or isinstance(node.src, parser.IndexedPortDecl):
            src_owns = True
        if not src_owns and not dst_owns or src_owns and dst_owns:
            semantic.status.error('Cannot infer edge ownership', node.name.loc)
        e.src_owns = src_owns
        e.src = cls.visit(node.src, e, True, src_owns, semantic)
        e.dst = cls.visit(node.dst, e, False, dst_owns, semantic)
        e.src.other_side = e.dst
        e.dst.other_side = e.src
        return e

    @dispatch(parser.File)
    def visitFile(cls, node, semantic):
        structs = []
        edges = []
        for decl in node.decls:
            result = cls.visit(decl, semantic)
            if isinstance(result, model.Struct):
                structs.append(result)
            elif isinstance(result, model.Edge):
                edges.append(result)
            else:
                assert False, result
        return model.Program(structs, edges)


def process_file(name, src, f):
    status = ritual.interpreter.location.CompileStatus()
    loc = status.add_source(name, src)
    # TODO link to parser.
    semantic = SemanticPass(status)
    IndexGlobals.visit(f, semantic)
    semantic.status.halt_if_errors()
    prog = ResolveTypes.visit(f, semantic)
    semantic.status.halt_if_errors()

    out = io.StringIO()
    generate_python.generate(prog, out)
    return out.getvalue()

def compile_source(name, src, out_dict):
    code = compile(src, name, 'exec')
    exec(code, out_dict)