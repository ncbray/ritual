from ritual.base import TreeMeta
from collections import OrderedDict


class ModuleType(object, metaclass=TreeMeta):
    __schema__ = ''


class IntrinsicTypeTag(object, metaclass=TreeMeta):
    __schema__ = 'name:string'


class IntegerTypeTag(object, metaclass=TreeMeta):
    __schema__ = 'name:string width:int unsigned:bool'


class FloatTypeTag(object, metaclass=TreeMeta):
    __schema__ = 'name:string width:int'


class UserTypeTag(object, metaclass=TreeMeta):
    __schema__ = ''


TypeTag = (IntrinsicTypeTag, IntegerTypeTag, FloatTypeTag, UserTypeTag)


class TupleType(object, metaclass=TreeMeta):
    __schema__ = 'children:[]Type'


class FunctionType(object, metaclass=TreeMeta):
    __schema__ = 'params:[]Type rt:Type'


class Field(object, metaclass=TreeMeta):
    __schema__ = 'loc:int name:string t:Type@[no_init] owner:Struct@[backedge]'


class Struct(object, metaclass=TreeMeta):
    __schema__ = 'loc:int name:string is_ref:bool module:Module tag:TypeTag parent:?Struct@[backedge, no_init] fields:[]Field@[no_init] methods:[]Function@[no_init] namespace:OrderedDict@[simple_init]'


class PoisonType(object, metaclass=TreeMeta):
    __schema__ = ''


Type = (ModuleType, TupleType, FunctionType, Struct, PoisonType)


class GetLocal(object, metaclass=TreeMeta):
    __schema__ = 'loc:int lcl:Local@[backedge] t:Type@[backedge]'


class GetType(object, metaclass=TreeMeta):
    __schema__ = 'loc:int t:Type@[backedge]'


class GetFunction(object, metaclass=TreeMeta):
    __schema__ = 'loc:int f:BaseFunction@[backedge]'


class GetModule(object, metaclass=TreeMeta):
    __schema__ = 'loc:int m:Module@[backedge]'


class GetField(object, metaclass=TreeMeta):
    __schema__ = 'loc:int expr:Expr field:Field@[backedge] t:Type@[backedge]'


class GetMethod(object, metaclass=TreeMeta):
    __schema__ = 'loc:int expr:Expr func:BaseFunction@[backedge]'


class DirectCall(object, metaclass=TreeMeta):
    __schema__ = 'loc:int f:BaseFunction@[backedge] args:[]Expr t:Type@[backedge]'


class DirectMethodCall(object, metaclass=TreeMeta):
    __schema__ = 'loc:int expr:Expr f:BaseFunction@[backedge] args:[]Expr t:Type@[backedge]'

class IndirectMethodCall(object, metaclass=TreeMeta):
    __schema__ = 'loc:int expr:Expr name:string args:[]Expr t:Type@[backedge]'

class Constructor(object, metaclass=TreeMeta):
    __schema__ = 'loc:int t:Struct@[backedge] args:[]Expr'


class BooleanLiteral(object, metaclass=TreeMeta):
    __schema__ = 'loc:int value:bool t:Type@[backedge]'


class TupleLiteral(object, metaclass=TreeMeta):
    __schema__ = 'loc:int t:TupleType@[backedge] args:[]Expr'


class FloatLiteral(object, metaclass=TreeMeta):
    __schema__ = 'loc:int text:string value:float t:Type@[backedge]'


class IntLiteral(object, metaclass=TreeMeta):
    __schema__ = 'loc:int value:int t:Type@[backedge]'


class StringLiteral(object, metaclass=TreeMeta):
    __schema__ = 'loc:int value:string t:Type@[backedge]'


class Assign(object, metaclass=TreeMeta):
    __schema__ = 'loc:int target:Target value:Expr'


class Sequence(object, metaclass=TreeMeta):
    __schema__ = 'loc:int children:[]Expr t:Type@[backedge]'


class PrefixOp(object, metaclass=TreeMeta):
    __schema__ = 'loc:int op:string expr:Expr t:Type@[backedge]'


class BinaryOp(object, metaclass=TreeMeta):
    __schema__ = 'loc:int left:Expr op:string right:Expr t:Type@[backedge]'


class If(object, metaclass=TreeMeta):
    __schema__ = 'loc:int cond:Expr tbody:Expr fbody:Expr t:Type@[backedge]'


class While(object, metaclass=TreeMeta):
    __schema__ = 'loc:int cond:Expr body:Expr'


class StructMatch(object, metaclass=TreeMeta):
    __schema__ = 't:Struct@[backedge]'


Matcher = (StructMatch,)


class Case(object, metaclass=TreeMeta):
    __schema__ = 'loc:int matcher:Matcher expr:Expr'


class Match(object, metaclass=TreeMeta):
    __schema__ = 'loc:int cond:Expr cases:[]Case rt:Type'


class PoisonExpr(object, metaclass=TreeMeta):
    __schema__ = ''


Expr = (GetLocal, GetType, GetFunction, GetModule, GetField, GetMethod, DirectCall, DirectMethodCall, IndirectMethodCall, Constructor, BooleanLiteral, TupleLiteral, FloatLiteral, IntLiteral, StringLiteral, Assign, Sequence, PrefixOp, BinaryOp, If, While, Match, PoisonExpr)


class SetLocal(object, metaclass=TreeMeta):
    __schema__ = 'loc:int lcl:Local@[backedge]'


class SetField(object, metaclass=TreeMeta):
    __schema__ = 'loc:int expr:Expr field:Field@[backedge]'


class DestructureTuple(object, metaclass=TreeMeta):
    __schema__ = 'loc:int args:[]Target'


class DestructureStruct(object, metaclass=TreeMeta):
    __schema__ = 'loc:int t:Type args:[]Target'


class PoisonTarget(object, metaclass=TreeMeta):
    __schema__ = ''


Target = (SetLocal, SetField, DestructureTuple, DestructureStruct, PoisonTarget)


class Param(object, metaclass=TreeMeta):
    __schema__ = 'loc:int name:string t:Type lcl:Local@[no_init]'


class Local(object, metaclass=TreeMeta):
    __schema__ = 'loc:int name:string t:Type'
    

class Function(object, metaclass=TreeMeta):
    __schema__ = 'loc:int name:string module:Module overrides:Function@[no_init] is_overridden:bool@[no_init] self:Param@[no_init] params:[]Param@[no_init] t:FunctionType@[no_init] locals:[]Local@[no_init] body:Expr@[no_init]'


class ExternFunction(object, metaclass=TreeMeta):
    __schema__ = 'loc:int name:string module:Module self:Param@[no_init] params:[]Param@[no_init] t:FunctionType@[no_init]'


BaseFunction = (Function, ExternFunction)


class Test(object, metaclass=TreeMeta):
    __schema__ = 'desc:string locals:[]Local@[no_init] body:Expr@[no_init]'


class Module(object, metaclass=TreeMeta):
    __schema__ = 'name:string structs:[]Struct@[no_init] extern_funcs:[]ExternFunction@[no_init] funcs:[]Function@[no_init] tests:[]Test@[no_init] namespace:OrderedDict@[simple_init]'


class Program(object, metaclass=TreeMeta):
    __schema__ = 'modules:[]Module@[no_init] entrypoint:Function@[no_init]'
