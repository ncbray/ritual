from ritual.base import TreeMeta
from collections import OrderedDict


class ModuleType(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


class IntrinsicType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string'


class TupleType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'children:[]Type'


class FunctionType(object):
    __metaclass__ = TreeMeta
    __schema__ = 'params:[]Type rt:Type'


class Field(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string t:Type'


class Struct(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int name:string module:Module fields:[]Field@[no_init] namespace:OrderedDict@[simple_init]'


class PoisonType(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Type = (IntrinsicType, ModuleType, TupleType, FunctionType, Struct, PoisonType)


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
    __schema__ = 'loc:int expr:Expr field:Field'


class DirectCall(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int f:BaseFunction@[backedge] args:[]Expr'


class Constructor(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int t:Struct@[backedge] args:[]Expr'


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


class BinaryOp(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int left:Expr op:string right:Expr'


class While(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int cond:Expr body:Expr'


class PoisonExpr(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Expr = (GetLocal, GetType, GetFunction, GetModule, GetField, DirectCall, Constructor, TupleLiteral, FloatLiteral, IntLiteral, StringLiteral, Assign, Sequence, BinaryOp, While, PoisonExpr)


class SetLocal(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int lcl:Local@[backedge]'


class DestructureTuple(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int args:[]Target'


class PoisonTarget(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Target = (SetLocal, DestructureTuple, PoisonTarget)


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
