from ritual.base import TreeMeta
from collections import OrderedDict


class ModuleType(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


class IntrinsicType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string'


class IntegerType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string width:int unsigned:bool'


class FloatType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string width:int'


class TupleType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'children:[]Type'


class FunctionType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'params:[]Type rt:Type'


class Field(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string t:Type owner:Struct@[backedge]'


class Struct(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string is_ref:bool module:Module parent:?Struct@[backedge, no_init] fields:[]Field@[no_init] namespace:OrderedDict@[simple_init]'


class PoisonType(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Type = (IntrinsicType, IntegerType, FloatType, ModuleType, TupleType, FunctionType, Struct, PoisonType)


class GetLocal(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int lcl:Local@[backedge]'


class GetType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int t:Type@[backedge]'


class GetFunction(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int f:BaseFunction@[backedge]'


class GetModule(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int m:Module@[backedge]'


class GetField(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int expr:Expr field:Field@[backedge]'


class DirectCall(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int f:BaseFunction@[backedge] args:[]Expr'


class Constructor(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int t:Struct@[backedge] args:[]Expr'


class BooleanLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int value:bool'


class TupleLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int t:TupleType@[backedge] args:[]Expr'


class FloatLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int text:string value:float'


class IntLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int value:int'


class StringLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int value:basestring'


class Assign(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int target:Target value:Expr'


class Sequence(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int children:[]Expr'


class PrefixOp(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int op:string expr:Expr'


class BinaryOp(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int left:Expr op:string right:Expr t:Type'


class If(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int cond:Expr t:Expr f:Expr rt:Type'


class While(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int cond:Expr body:Expr'


class PoisonExpr(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Expr = (GetLocal, GetType, GetFunction, GetModule, GetField, DirectCall, Constructor, BooleanLiteral, TupleLiteral, FloatLiteral, IntLiteral, StringLiteral, Assign, Sequence, PrefixOp, BinaryOp, If, While, PoisonExpr)


class SetLocal(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int lcl:Local@[backedge]'


class SetField(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int expr:Expr field:Field@[backedge]'


class DestructureTuple(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int args:[]Target'


class PoisonTarget(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Target = (SetLocal, SetField, DestructureTuple, PoisonTarget)


class Param(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string t:Type lcl:Local@[no_init]'


class Local(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string t:Type'
    

class Function(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string module:Module params:[]Param@[no_init] t:FunctionType@[no_init] locals:[]Local@[no_init] body:Expr@[no_init]'


class ExternFunction(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string module:Module params:[]Param@[no_init] t:FunctionType@[no_init]'


BaseFunction = (Function, ExternFunction)


class Test(object):
    __metaclass__ = TreeMeta
    __schema__ = 'desc:string locals:[]Local@[no_init] body:Expr@[no_init]'


class Module(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string structs:[]Struct@[no_init] extern_funcs:[]ExternFunction@[no_init] funcs:[]Function@[no_init] tests:[]Test@[no_init] namespace:OrderedDict@[simple_init]'


class Program(object):
    __metaclass__ = TreeMeta
    __schema__ = 'modules:[]Module@[no_init] entrypoint:Function@[no_init]'
