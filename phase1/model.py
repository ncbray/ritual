import base
import phase0.parser


class Decl(object):
    __slots__ = []


class TypeRef(object):
    __slots__ = []


class NameRef(TypeRef):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'


class ListRef(TypeRef):
    __metaclass__ = base.TreeMeta
    __schema__ = 'ref:TypeRef'


class FieldDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string t:TypeRef'


class StructDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string fields:[]FieldDecl'


class UnionDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string refs:[]TypeRef'


class Extern(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string params:[]TypeRef rt:TypeRef'


class RuleDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string rt:TypeRef body:phase0.parser.Matcher'


class File(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'decls:[]Decl'

def registerTypes(p):
    p.rule(phase0.parser.Native('NameRef', NameRef))
    p.rule(phase0.parser.Native('ListRef', ListRef))
    p.rule(phase0.parser.Native('FieldDecl', FieldDecl))
    p.rule(phase0.parser.Native('StructDecl', StructDecl))
    p.rule(phase0.parser.Native('UnionDecl', UnionDecl))
    p.rule(phase0.parser.Native('Extern', Extern))
    p.rule(phase0.parser.Native('RuleDecl', RuleDecl))
    p.rule(phase0.parser.Native('File', File))
