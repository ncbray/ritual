from base import TreeMeta
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


class PoisonType(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Type = (IntrinsicType, ModuleType, TupleType, FunctionType, PoisonType)


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


class DirectCall(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int f:BaseFunction@[backedge] args:[]Expr'


class TupleLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int t:TupleType@[backedge] args:[]Expr'


class IntLiteral(object):
    __metaclass__ = TreeMeta
    __schema__ = 'loc:int value:int'


class PoisonExpr(object):
    __metaclass__ = TreeMeta
    __schema__ = ''


Expr = (GetLocal, GetType, GetFunction, GetModule, DirectCall, TupleLiteral, IntLiteral, PoisonExpr)


class Param(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string t:Type lcl:Local@[no_init]'


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


class Module(object):
    __metaclass__ = TreeMeta
    __schema__ = 'name:string functions:[]Function@[no_init] namespace:OrderedDict@[simple_init]'


class Program(object):
    __metaclass__ = TreeMeta
    __schema__ = 'modules:[]Module@[no_init]'
