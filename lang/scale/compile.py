from base import TypeDispatcher, dispatch
import cStringIO
import os.path
import interpreter.location

import parser
import semantic
import generate_cpp

class ModuleLoader(object):
    def __init__(self, root, status):
        self.root = root
        self.status = status
        self.searched = set()
        self.pending = []

    def module_file(self, path):
        full = os.path.join(self.root, '/'.join(path) + '.scale')
        if os.path.exists(full):
            return full

    def require_module(self, path, loc):
        path = tuple(path)
        if path in self.searched:
            return
        fn = self.module_file(path)
        if fn:
            self.pending.append((path, fn))
        else:
            self.status.error('cannot find module "%s"' % '.'.join(path), loc)


class FindImports(object):
    __metaclass__ = TypeDispatcher

    @dispatch(parser.ImportDecl)
    def visitImportDecl(cls, node, loader):
        loader.require_module(node.path, node.loc)

    @dispatch(parser.FuncDecl, parser.ExternFuncDecl, parser.StructDecl, parser.TestDecl)
    def visiIgnore(cls, node, loader):
        pass

    @dispatch(parser.Module)
    def visitModule(cls, node, loader):
        for decl in node.decls:
            cls.visit(decl, loader)


def parse_file(module_name, path, status):
    with open(path) as f:
        text = f.read()
    loc = status.add_source(path, text)
    result = parser.p.parse('module', [module_name, path], text, loc)
    if not result.ok:
        status.error('unexpected character', result.loc)
    return result.value


def frontend(root, entrypoint, status):
    assert isinstance(entrypoint, list), entrypoint

    loader = ModuleLoader(root, status)
    loader.require_module(entrypoint, None)
    status.halt_if_errors()

    # Parse and resolve imports
    modules = []
    while loader.pending:
        module_path, fn = loader.pending.pop(0)
        m = parse_file('.'.join(module_path), fn, status)
        if m:
            FindImports.visit(m, loader)
            modules.append(m)
    status.halt_if_errors()

    p = semantic.process(modules, status)
    status.halt_if_errors()
    return p


def full_compile(root, entrypoint):
    status = interpreter.location.CompileStatus()
    p = frontend(root, entrypoint, status)
    status.halt_if_errors()

    out = cStringIO.StringIO()
    generate_cpp.generate_source(p, out)
    return out.getvalue()
