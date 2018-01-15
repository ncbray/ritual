import base
import interpreter


class Matcher(object):
    __slots__ = []


class Sequence(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'children:[]Matcher'


class Choice(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'children:[]Matcher'


class Repeat(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher min:int max:int'


class Call(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher args:[]Matcher'


class Range(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'lower:rune upper:rune'


class Character(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'ranges:[]Range invert:bool'


class MatchValue(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher'


class Slice(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher'


class Get(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'


class Set(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher name:string'


class Append(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher name:string'


class List(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 't:TypeRef args:[]Matcher'


class Literal(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'value:*'


class TypeRef(object):
    __slots__ = []


class NameRef(TypeRef):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'


class ListRef(TypeRef):
    __metaclass__ = base.TreeMeta
    __schema__ = 'ref:TypeRef'


class Decl(object):
    __slots__ = []


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
    __schema__ = 'name:string rt:TypeRef body:Matcher attrs:[]Attribute'


class File(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'decls:[]Decl'


class Attribute(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'


def registerTypes(p):
    p.rule(interpreter.Native('Range', Range))
    p.rule(interpreter.Native('Character', Character))
    p.rule(interpreter.Native('MatchValue', MatchValue))
    p.rule(interpreter.Native('Repeat', Repeat))
    p.rule(interpreter.Native('Sequence', Sequence))
    p.rule(interpreter.Native('Choice', Choice))
    p.rule(interpreter.Native('Literal', Literal))
    p.rule(interpreter.Native('Slice', Slice))
    p.rule(interpreter.Native('List', List))
    p.rule(interpreter.Native('Call', Call))
    p.rule(interpreter.Native('Get', Get))
    p.rule(interpreter.Native('Set', Set))
    p.rule(interpreter.Native('Append', Append))
    p.rule(interpreter.Native('NameRef', NameRef))
    p.rule(interpreter.Native('ListRef', ListRef))
    p.rule(interpreter.Native('FieldDecl', FieldDecl))
    p.rule(interpreter.Native('StructDecl', StructDecl))
    p.rule(interpreter.Native('UnionDecl', UnionDecl))
    p.rule(interpreter.Native('ExternDecl', ExternDecl))
    p.rule(interpreter.Native('RuleDecl', RuleDecl))
    p.rule(interpreter.Native('File', File))
    p.rule(interpreter.Native('Attribute', Attribute))
