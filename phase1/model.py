import base
import interpreter


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


class ExternDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string params:[]TypeRef rt:TypeRef'


class RuleDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string rt:TypeRef body:interpreter.Matcher, attrs:[]Attribute'


class File(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'decls:[]Decl'


class Attribute(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'


def registerTypes(p):
    p.rule(interpreter.Native('NameRef', NameRef))
    p.rule(interpreter.Native('ListRef', ListRef))
    p.rule(interpreter.Native('FieldDecl', FieldDecl))
    p.rule(interpreter.Native('StructDecl', StructDecl))
    p.rule(interpreter.Native('UnionDecl', UnionDecl))
    p.rule(interpreter.Native('ExternDecl', ExternDecl))
    p.rule(interpreter.Native('RuleDecl', RuleDecl))
    p.rule(interpreter.Native('File', File))
    p.rule(interpreter.Native('Attribute', Attribute))
