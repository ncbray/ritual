from base import TypeDispatcher, dispatch
import base.io
import model


def remote_name(port):
    if isinstance(port, model.ScalarPort):
        assert len(port.names) == 1, port
        name = port.names[0]
    else:
        name = port.name
    return '_' + name


def generate_edge_setter(expr, port, port_name, out):
    out.write('assert isinstance(value, %s) or value is None, value\n' % port.t.name)
    out.write('if %s is not None:\n' % expr)
    with out.block('pass\n'):
        if isinstance(port, model.BagPort):
            out.write('%s.%s.remove(self)\n' % (expr, port_name))
        elif isinstance(port, model.ScalarPort):
            out.write('%s.%s = None\n' % (expr, port_name))
        else:
            assert False, port
    out.write('%s = value\n' % expr)
    out.write('if %s is not None:\n' % expr)
    with out.block('pass\n'):
        if isinstance(port, model.BagPort):
            out.write('%s.%s.append(self)\n' % (expr, port_name))
        elif isinstance(port, model.ScalarPort):
            out.write('assert %s.%s is None, %s.%s\n' % (expr, port_name, expr, port_name))
            out.write('%s.%s = self\n' % (expr, port_name))
        else:
            assert False, port


class GeneratePython(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.Struct)
    def visitStruct(cls, node, out):
        out.write('\n\n')
        out.write('class %s(object):\n' % node.name)
        slots = []
        for p in node.ports:
            if isinstance(p, model.ScalarPort):
                for name in p.names:
                    slots.append('_' + name)
            else:
                slots.append('_' + p.name)
        with out.block('pass\n'):
            out.write('__slots__ = [%s]\n' % ', '.join(['\'%s\'' % s for s in slots]))

            # Constructor
            params = ['self']
            for p in node.ports:
                if isinstance(p, model.IndexedPort):
                    params.append('num_' + p.name)
            out.write('\ndef __init__(%s):\n' % ', '.join(params))
            with out.block('pass\n'):
                for p in node.ports:
                    if isinstance(p, model.ScalarPort):
                        for i, name in enumerate(p.names):
                            if p.owner:
                                out.write('self._%s = %s(self, %d)\n' % (name, p.edge.name, i))
                            else:
                                out.write('self._%s = None\n' % (name,))
                    elif isinstance(p, model.IndexedPort):
                        out.write('self._%s = tuple([%s(self, i) for i in range(num_%s)])\n' % (p.name, p.edge.name, p.name))                        
                    else:
                        out.write('self._%s = []\n' % (p.name,))

            # Accessors
            for p in node.ports:
                if isinstance(p, model.ScalarPort):
                    #other_side = 'dst' if p.src else 'src'
                    for name in p.names:
                        out.write('\n@property\ndef %s(self):\n' % name)
                        with out.block('pass\n'):
                            out.write('return self._%s\n' % (name,))
                else:
                    name = p.name
                    out.write('\n@property\ndef %s(self):\n' % name)
                    with out.block('pass\n'):
                        out.write('return self._%s\n' % (name,))


    @dispatch(model.Edge)
    def visitEdge(cls, node, out):
        out.write('\n\n')
        out.write('class %s(object):\n' % node.name)
        slots = ['_src', '_index', '_dst']
        with out.block('pass\n'):
            out.write('__slots__ = [%s]\n' % ', '.join(['\'%s\'' % s for s in slots]))
            out.write('\n')
            out.write('def __init__(self, owner, index):\n')
            with out.block('pass\n'):
                if node.src_owns:
                    out.write('assert isinstance(owner, %s), owner\n' % node.src.t.name)
                    out.write('assert isinstance(index, int), index\n')
                    out.write('self._src = owner\n')
                    out.write('self._index = index\n')
                    out.write('self._dst = None\n')
                else:
                    out.write('assert isinstance(owner, %s), owner\n' % node.dst.t.name)
                    out.write('assert isinstance(index, int), index\n')
                    out.write('self._src = None\n')
                    out.write('self._index = index\n')
                    out.write('self._dst = owner\n')

            out.write('\n@property\ndef src(self):\n')
            with out.block('pass\n'):
                out.write('return self._src\n')

            if not node.src_owns:
                out.write('\n@src.setter\ndef src(self, value):\n')
                with out.block('pass\n'):
                    generate_edge_setter('self._src', node.src, remote_name(node.src), out)

            out.write('\n@property\ndef dst(self):\n')
            with out.block('pass\n'):
                out.write('return self._dst\n')

            if node.src_owns:
                out.write('\n@dst.setter\ndef dst(self, value):\n')
                with out.block('pass\n'):
                    generate_edge_setter('self._dst', node.dst, remote_name(node.dst), out)

    @dispatch(model.Program)
    def visitProgram(cls, node, out):
        for s in node.structs:
            cls.visit(s, out)

        for e in node.edges:
            cls.visit(e, out)

def generate(p, out):
    GeneratePython.visit(p, base.io.TabbedWriter(out))
