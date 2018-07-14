from ritual import base
import ritual.interpreter


types = []
def register(cls):
    types.append(cls)
    return cls


@register
class Token(object, metaclass=base.TreeMeta):
    __schema__ = 'loc:int text:string'


class Matcher(object):
    __slots__ = []


@register
class Sequence(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'children:[]Matcher'


@register
class Choice(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'children:[]Matcher'


@register
class Repeat(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'expr:Matcher min:int max:int'


@register
class Call(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int expr:Matcher args:[]Matcher'


class DirectCall(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int func:CallableType@[backedge] args:[]Matcher'


@register
class Range(object, metaclass=base.TreeMeta):
    __schema__ = 'lower:rune upper:rune'


@register
class Character(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int ranges:[]Range invert:bool'


@register
class MatchValue(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int expr:Matcher'


@register
class Slice(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int expr:Matcher'


@register
class Lookahead(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int expr:Matcher invert:bool'


@register
class Get(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'name:Token'


@register
class Set(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'expr:Matcher name:Token'


@register
class Append(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'expr:Matcher name:Token'


@register
class GetLocal(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int lcl:Local@[backedge]'


@register
class SetLocal(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'expr:Matcher lcl:Local@[backedge]'


@register
class AppendLocal(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'expr:Matcher lcl:Local@[backedge]'


@register
class ListLiteral(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int t:TypeRef args:[]Matcher'


@register
class Location(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int'


@register
class StringLiteral(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int value:string'


@register
class RuneLiteral(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int value:rune'


@register
class IntLiteral(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int value:int'


@register
class BoolLiteral(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int value:bool'


@register
class StructLiteral(Matcher, metaclass=base.TreeMeta):
    __schema__ = 'loc:int t:NameRef args:[]Matcher'


class TypeRef(object):
    __slots__ = []


@register
class NameRef(TypeRef, metaclass=base.TreeMeta):
    __schema__ = 'name:Token'


@register
class ListRef(TypeRef, metaclass=base.TreeMeta):
    __schema__ = 'ref:TypeRef'


class DirectRef(TypeRef, metaclass=base.TreeMeta):
    __schema__ = 'loc:int t:Type@[backedge]'


class Decl(object):
    __slots__ = []


@register
class FieldDecl(Decl, metaclass=base.TreeMeta):
    __schema__ = 'name:Token t:TypeRef'


@register
class StructDecl(Decl, metaclass=base.TreeMeta):
    __schema__ = 'name:Token fields:[]FieldDecl'


@register
class UnionDecl(Decl, metaclass=base.TreeMeta):
    __schema__ = 'name:Token refs:[]TypeRef'


@register
class Param(object, metaclass=base.TreeMeta):
    __schema__ = 'name:Token t:TypeRef'


@register
class ExternDecl(Decl, metaclass=base.TreeMeta):
    __schema__ = 'name:Token params:[]Param rt:TypeRef'


@register
class RuleDecl(Decl, metaclass=base.TreeMeta):
    __schema__ = 'name:Token params:[]Param rt:TypeRef body:Matcher attrs:[]Attribute'


@register
class File(object, metaclass=base.TreeMeta):
    __schema__ = 'decls:[]Decl'


@register
class Attribute(object, metaclass=base.TreeMeta):
    __schema__ = 'name:Token'


class Type(object):
    __slots__ = []


class IntrinsicType(Type, metaclass=base.TreeMeta):
    __schema__ = 'name:string list_cache:ListType@[no_init, backedge]'


class Field(object, metaclass=base.TreeMeta):
    __schema__ = 'name:string t:Type@[backedge]'


class StructType(Type, metaclass=base.TreeMeta):
    __schema__ = 'name:string fields:[]Field unions:[]UnionType@[no_init, backedge] list_cache:ListType@[no_init, backedge]'


class UnionType(Type, metaclass=base.TreeMeta):
    __schema__ = 'name:string types:[]Type@[backedge] list_cache:ListType@[no_init, backedge]'


class ListType(Type, metaclass=base.TreeMeta):
    __schema__ = 't:Type list_cache:ListType@[no_init, backedge]'


class CallableType(Type):
    __slots__ = []


class ExternType(CallableType, metaclass=base.TreeMeta):
    __schema__ = 'name:string params:[]Type@[no_init, backedge] rt:Type@[no_init, backedge]'


class Local(object, metaclass=base.TreeMeta):
    __schema__ = 'loc:int name:string t:Type'


class RuleType(CallableType, metaclass=base.TreeMeta):
    __schema__ = 'name:string params:[]Type@[no_init, backedge] rt:Type@[no_init, backedge] locals:[]Local@[no_init]'


class VoidType(Type, metaclass=base.TreeMeta):
    __schema__ = ''


class PoisonType(Type, metaclass=base.TreeMeta):
    __schema__ = ''


def registerTypes(p):
    for t in types:
        p.rule(ritual.interpreter.Native(t.__name__, [ritual.interpreter.Param(slot) for slot in t.__slots__], t))
