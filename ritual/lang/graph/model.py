from ritual.base import TreeMeta


class ScalarPort(object):
    __metaclass__ = TreeMeta
    __schema__ = 'names:[]string t:Struct@[backedge] edge:Edge@[backedge] src:bool owner:bool other_side:Port@[no_init, backedge]'


class IndexedPort(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string t:Struct@[backedge] edge:Edge@[backedge] src:bool owner:bool other_side:Port@[no_init, backedge]'


class BagPort(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string t:Struct@[backedge] edge:Edge@[backedge] src:bool other_side:Port@[no_init, backedge]'


Port = (ScalarPort, IndexedPort, BagPort)


class Struct(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string ports:[]Port@[no_init] ns:StrictNamespace'


class Edge(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string src:Port@[no_init, backedge] dst:Port@[no_init, backedge] src_owns:bool@[no_init]'


class Program(object):
    __metaclass__ = TreeMeta
    __schema__ = 'structs:[]Struct edges:[]Edge'


class StrictNamespace(object):
    def __init__(self):
        self.order = []
        self.index = {}

    def define(self, tok, value, status):
        if tok.text in self.index:
            status.error('tried to redefine "%s"' % tok.text, tok.loc)
        else:
            self.order.append(value)
            self.index[tok.text] = value
