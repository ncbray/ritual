import base
import interpreter

types = []

def register(cls):
    types.append(cls)
    return cls

class Matcher(object):
    __slots__ = []

@register
class Sequence(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'children:[]Matcher'

@register
class Choice(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'children:[]Matcher'

@register
class Repeat(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher min:int max:int'

@register
class Call(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher args:[]Matcher'

@register
class Range(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'lower:rune upper:rune'

@register
class Character(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'ranges:[]Range invert:bool'

@register
class MatchValue(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher'

@register
class Slice(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher'

@register
class Get(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'

@register
class Set(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher name:string'

@register
class Append(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher name:string'


@register
class ListLiteral(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 't:TypeRef args:[]Matcher'


@register
class StringLiteral(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'value:string'


@register
class RuneLiteral(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'value:rune'

@register
class IntLiteral(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'value:int'

@register
class BoolLiteral(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'value:bool'

@register
class StructLiteral(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 't:NameRef args:[]Matcher'


class TypeRef(object):
    __slots__ = []


@register
class NameRef(TypeRef):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'

@register
class ListRef(TypeRef):
    __metaclass__ = base.TreeMeta
    __schema__ = 'ref:TypeRef'


class Decl(object):
    __slots__ = []

@register
class FieldDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string t:TypeRef'

@register
class StructDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string fields:[]FieldDecl'

@register
class UnionDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string refs:[]TypeRef'

@register
class ExternDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string params:[]TypeRef rt:TypeRef'

@register
class RuleDecl(Decl):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string rt:TypeRef body:Matcher attrs:[]Attribute'

@register
class File(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'decls:[]Decl'

@register
class Attribute(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'


class Type(object):
    __slots__ = []


class IntrinsicType(Type):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string list_cache:ListType@[no_init, backedge]'


class Field(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string t:Type@[backedge]'


class StructType(Type):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string fields:[]Field list_cache:ListType@[no_init, backedge]'


class UnionType(Type):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string types:[]Type@[backedge] list_cache:ListType@[no_init, backedge]'


class ListType(Type):
    __metaclass__ = base.TreeMeta
    __schema__ = 't:Type list_cache:ListType@[no_init, backedge]'


class CallableType(Type):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string params:[]Type@[no_init, backedge] rt:Type@[no_init, backedge]'


class VoidType(Type):
    __metaclass__ = base.TreeMeta
    __schema__ = ''


def registerTypes(p):
    for t in types:
        p.rule(interpreter.Native(t.__name__, t))
