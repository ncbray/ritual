from ritual.base import TypeDispatcher, dispatch
import cStringIO
import os.path
import ritual.interpreter.location

import parser
import semantic
import generate_cpp

class ModuleLoader(object):
    def __init__(self, system, root, status):
        self.system = system
        self.root = root
        self.status = status
        self.was_enqueued = set()
        self.pending = []
        self.files = set([system, root])

    def check_exists(self, root, path):
        for i in range(1, len(path)-1):
            partial = os.path.join(root, *path[:i])
            if not os.path.exists(partial):
                return None
            self.files.add(partial)

        full = os.path.join(root, '/'.join(path) + '.scale')
        if os.path.exists(full):
            self.files.add(full)
            return full

    def module_file(self, path):
        for root in [self.root, self.system]:
            full = self.check_exists(root, path)
            if full:
                return full

    def require_module(self, path, loc):
        path = tuple(path)
        if path in self.was_enqueued:
            return
        fn = self.module_file(path)
        if fn:
            self.pending.append((path, fn))
            self.was_enqueued.add(path)
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


def frontend(system, root, entrypoint, status):
    assert isinstance(entrypoint, list), entrypoint

    loader = ModuleLoader(system, root, status)
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

    # Identify the entrypoint.
    for m in p.modules:
        if m.name != '.'.join(entrypoint):
            continue
        for f in m.funcs:
            if f.name != 'main':
                continue
            if f.params:
                continue
            p.entrypoint = f
        break

    if not p.entrypoint:
        status.error('cannot identify entrypoint')
    status.halt_if_errors()

    return p, loader.files
