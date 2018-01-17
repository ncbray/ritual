import cStringIO

from base import TypeDispatcher, dispatch, python_types
import interpreter
import model

class Block(object):
    def __init__(self, out):
        assert isinstance(out, TabbedWriter), out
        self.out = out

    def __enter__(self):
        self.out.indent()

    def __exit__(self, type, value, traceback):
        self.out.dedent()


class TabbedWriter(object):
    def __init__(self, out):
        self.out = out
        self.indent_level = 0
        self.indent_text = ''
        self.buffer = ''

    def indent(self):
        #assert not self.dirty
        self.indent_level += 1
        self.indent_text = self.indent_level * '    '

    def dedent(self):
        # Can't check dirty because this may be an exception.
        self.indent_level -= 1
        self.indent_text = self.indent_level * '    '

    def block(self):
        return Block(self)

    # TODO behaves badly when accumulating whitespace.
    def write(self, text):
        for l in text.splitlines(True):
            self.buffer += l
            eol = l.endswith('\n')
            if not eol:
                return
            b = self.buffer.rstrip()
            self.buffer = ''
            if b:
                self.out.write(self.indent_text)
                self.out.write(b)
            self.out.write('\n')


class TreeType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.NameRef)
    def visitNameRef(cls, node):
        return node.name

    @dispatch(model.ListRef)
    def visitListRef(cls, node):
        return '[]' + cls.visit(node.ref)


class PythonType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.NameRef)
    def visitNameRef(cls, node):
        return python_types.get(node.name, node.name)


alternate_names = {
    'ListLiteral': 'List',
    'StringLiteral': 'Literal',
    'RuneLiteral': 'Literal',
    'IntLiteral': 'Literal',
    'BoolLiteral': 'Literal',
}

class GenerateInterpreter(object):
    __metaclass__ = TypeDispatcher

    @dispatch(int, str, unicode, bool)
    def visitIntrinstic(cls, node):
        return node

    @dispatch(list)
    def visitList(cls, node):
        return [cls.visit(child) for child in node]

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node):
        return interpreter.Call(
            interpreter.Get(node.t.name),
            [cls.visit(arg) for arg in node.args]
        )

    @dispatch(model.Choice, model.Sequence, model.Repeat, model.Character,
        model.Range, model.MatchValue, model.ListLiteral, model.Slice,
        model.Call, model.Get, model.Set, model.Append, model.StringLiteral,
        model.RuneLiteral, model.IntLiteral, model.BoolLiteral)
    def visitNode(cls, node):
        # Assume named fields can be mapped to each other.
        n = type(node).__name__
        tgt = getattr(interpreter, alternate_names.get(n, n))
        slots = tgt.__slots__
        args = [cls.visit(getattr(node, slot)) for slot in slots]
        return tgt(*args)


class SerializeInterpreter(object):
    __metaclass__ = TypeDispatcher

    @dispatch(int, str, unicode, bool)
    def visitIntrinstic(cls, node, out):
        out.write(repr(node))

    @dispatch(list)
    def visitList(cls, node, out):
        if not node:
            out.write('[]')
        else:
            out.write('[\n')
            with out.block():
                for child in node:
                    cls.visit(child, out)
                    out.write(',\n')
            out.write(']')

    @dispatch(interpreter.Choice, interpreter.Sequence, interpreter.Repeat,
        interpreter.Character, interpreter.Range,
        interpreter.MatchValue, interpreter.List, interpreter.Slice,
        interpreter.Call, interpreter.Get, interpreter.Set,interpreter.Append,
        interpreter.Literal)
    def visitNode(cls, node, out):
        out.write('interpreter.%s(' % type(node).__name__)
        dirty = False
        slots = type(node).__slots__
        if len(slots) == 1:
            cls.visit(getattr(node, slots[0]), out)
        else:
            for slot in slots:
                child = getattr(node, slot)
                if dirty:
                    out.write(',\n')
                else:
                    out.write('\n')
                    out.indent()
                    dirty = True
                cls.visit(child, out)
            if dirty:
                out.write('\n')
                out.dedent()
        out.write(')')


class GeneratePython(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.StructDecl)
    def visitStruct(cls, node, out):
        out.write('\n\n')
        out.write('class %s(object):\n' % node.name)
        with out.block():
            out.write('__metaclass__ = base.TreeMeta\n')
            field_text = []
            for f in node.fields:
                field_text.append('%s:%s' % (f.name, TreeType.visit(f.t)))
            out.write('__schema__ = \'%s\'\n' % ' '.join(field_text))

    @dispatch(model.UnionDecl)
    def visitUnion(cls, node, out):
        out.write('\n\n')
        types = [PythonType.visit(t) for t in node.refs]
        out.write('%s = tuple([%s])\n' % (node.name, ', '.join(types)))

    @dispatch(model.File)
    def visitFile(cls, node, out):
        externs = []
        structs = []
        unions = []
        rules = []
        for decl in node.decls:
            if isinstance(decl, model.ExternDecl):
                externs.append(decl)
            elif isinstance(decl, model.StructDecl):
                structs.append(decl)
            elif isinstance(decl, model.UnionDecl):
                unions.append(decl)
            elif isinstance(decl, model.RuleDecl):
                rules.append(decl)
            else:
                assert False, decl

        out.write("""import base
import interpreter
""")
        for decl in structs:
            cls.visit(decl, out)

        for decl in unions:
            cls.visit(decl, out)

        out.write('\n\n')
        out.write('def buildParser(%s):\n' % ', '.join([e.name for e in externs]))
        with out.block():
            out.write('p = interpreter.Parser()\n')
            out.write('\n')
            for decl in rules:
                out.write('p.rule(interpreter.Rule(%r, ' % decl.name)
                interp = GenerateInterpreter.visit(decl.body)
                SerializeInterpreter.visit(interp, out)
                out.write('))\n')
            out.write('\n')
            out.write('# Register struct types\n')
            for decl in structs:
                out.write('p.rule(interpreter.Native(%r, %s))\n' % (decl.name, decl.name))
            out.write('\n')
            out.write('# Register externs\n')
            for decl in externs:
                out.write('p.rule(interpreter.Native(%r, %s))\n' % (decl.name, decl.name))

            out.write('\nreturn p\n')

        out.write('\n_isinstance = isinstance\n')
        out.write('\ndef isinstance(*args):\n')
        with out.block():
            out.write('return _isinstance(*args)\n')


def generate_source(f):
    out = TabbedWriter(cStringIO.StringIO())
    GeneratePython.visit(f, out)
    return out.out.getvalue()


def compile_source(name, src, out_dict):
    code = compile(src, name, 'exec')
    exec code in out_dict
