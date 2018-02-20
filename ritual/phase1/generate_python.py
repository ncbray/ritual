import cStringIO

from ritual.base import TypeDispatcher, dispatch, python_types
import ritual.base.io
from ritual import interpreter
import model

alternate_tree_names = {
    'location': 'int',
}

class TreeType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.IntrinsicType)
    def visitIntrinsicType(cls, node):
        name = node.name
        return alternate_tree_names.get(name, name)

    @dispatch(model.StructType)
    def visitStructType(cls, node):
        return node.name

    @dispatch(model.UnionType)
    def visitUnionType(cls, node):
        return node.name

    @dispatch(model.ListType)
    def visitListType(cls, node):
        return '[]' + cls.visit(node.t)

    @dispatch(model.DirectRef)
    def visitDirectRef(cls, node):
        return cls.visit(node.t)


class PythonType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.StructType)
    def visitStructType(cls, node):
        return node.name

    @dispatch(model.UnionType)
    def visitUnionType(cls, node):
        return node.name

    @dispatch(model.DirectRef)
    def visitDirectRef(cls, node):
        return cls.visit(node.t)


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

    @dispatch(model.Token)
    def visitToken(cls, node):
        return node.text

    @dispatch(model.StructLiteral)
    def visitStructLiteral(cls, node):
        return interpreter.Call(
            interpreter.Get(TreeType.visit(node.t)),
            [cls.visit(arg) for arg in node.args]
        )

    @dispatch(model.DirectCall)
    def visitDirectCall(cls, node):
        return interpreter.Call(
            interpreter.Get(node.func.name),
            cls.visit(node.args),
        )

    @dispatch(model.GetLocal)
    def visitGetLocal(cls, node):
        return interpreter.Get(node.lcl.name)

    @dispatch(model.SetLocal)
    def visitSetLocal(cls, node):
        return interpreter.Set(cls.visit(node.expr), node.lcl.name)

    @dispatch(model.AppendLocal)
    def visitAppendLocal(cls, node):
        return interpreter.Append(cls.visit(node.expr), node.lcl.name)

    @dispatch(model.Choice, model.Sequence, model.Repeat, model.Character,
        model.Range, model.MatchValue, model.ListLiteral, model.Slice,
        model.StringLiteral, model.RuneLiteral, model.IntLiteral, model.BoolLiteral,
        model.Location, model.Lookahead)
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
        interpreter.Call, interpreter.Get, interpreter.Set, interpreter.Append,
        interpreter.Literal, interpreter.Location, interpreter.Lookahead)
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
        out.write('class %s(object):\n' % node.name.text)
        with out.block():
            out.write('__metaclass__ = base.TreeMeta\n')
            field_text = []
            for f in node.fields:
                field_text.append('%s:%s' % (f.name.text, TreeType.visit(f.t)))
            out.write('__schema__ = \'%s\'\n' % ' '.join(field_text))

    @dispatch(model.UnionDecl)
    def visitUnion(cls, node, out):
        out.write('\n\n')
        types = [PythonType.visit(t) for t in node.refs]
        out.write('%s = tuple([%s])\n' % (node.name.text, ', '.join(types)))

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

        out.write("""from ritual import base, interpreter
""")
        for decl in structs:
            cls.visit(decl, out)

        for decl in unions:
            cls.visit(decl, out)

        out.write('\n\n')
        out.write('def buildParser(%s):\n' % ', '.join([e.name.text for e in externs]))
        with out.block():
            out.write('p = interpreter.Parser()\n')
            out.write('\n')
            for decl in rules:
                params = ['interpreter.Param(%r)' % p.name.text for p in decl.params]
                out.write('p.rule(interpreter.Rule(%r, [%s],' % (decl.name.text, ', '.join(params)))
                interp = GenerateInterpreter.visit(decl.body)
                SerializeInterpreter.visit(interp, out)
                out.write('))\n')
            out.write('\n')
            out.write('# Register struct types\n')
            for decl in structs:
                name = decl.name.text
                out.write('p.rule(interpreter.Native(%r, [interpreter.Param(slot) for slot in %s.__slots__], %s))\n' % (name, name, name))
            out.write('\n')
            out.write('# Register externs\n')
            for decl in externs:
                params = ['interpreter.Param(%r)' % p.name.text for p in decl.params]
                name = decl.name.text
                out.write('p.rule(interpreter.Native(%r, [%s], %s))\n' % (name, ', '.join(params), name))

            out.write('\nreturn p\n')

        out.write('\n_isinstance = isinstance\n')
        out.write('\ndef isinstance(*args):\n')
        with out.block():
            out.write('return _isinstance(*args)\n')


def generate_source(f):
    out = ritual.base.io.TabbedWriter(cStringIO.StringIO())
    GeneratePython.visit(f, out)
    return out.out.getvalue()


def compile_source(name, src, out_dict):
    code = compile(src, name, 'exec')
    exec code in out_dict
