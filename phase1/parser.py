from base import TypeDispatcher, dispatch

from phase0 import sugar
from phase0.parser import *

import model

p = Parser()

def rule(name, body):
    p.rule(Rule(name, sugar.text_match(body)))

def halt():
    import pdb;pdb.set_trace()

p.rule(Native('chr', unichr))
p.rule(Native('hex_to_int', lambda text: int(text, 16)))
p.rule(Native('dec_to_int', lambda text: int(text, 10)))
p.rule(Native('chars_to_string', lambda chars: ''.join(chars)))
p.rule(Native('halt', halt))

p.rule(Native('Range', Range))
p.rule(Native('Character', Character))
p.rule(Native('MatchValue', MatchValue))
p.rule(Native('Repeat', Repeat))
p.rule(Native('Sequence', Sequence))
p.rule(Native('Choice', Choice))
p.rule(Native('Literal', Literal))
p.rule(Native('Slice', Slice))
p.rule(Native('List', List))
p.rule(Native('Call', Call))
p.rule(Native('Get', Get))
p.rule(Native('Set', Set))
p.rule(Native('Append', Append))
p.rule(Native('Any', Any))

model.registerTypes(p)

rule('S', r'([[ \t\n\r]]|$"//";[[^\n]]*)*')
rule('hex_digit', r'[[0-9a-fA-F]]')
rule('ident', r'<[[a-zA-Z_]];[[a-zA-Z_0-9]]*>')
# TODO unicode escapes?
rule('escape_char', r"""[[\\]];
    ( [[n]]; chr(0x0A)
    | [[r]]; chr(0x0D)
    | [[t]]; chr(0x09)
    | [[0]]; chr(0x00)
    | [[\\]]; chr(0x5C)
    | [[x]]; chr(hex_to_int(<hex_digit(); hex_digit()>))
    )""")
rule('string_value', r"""[["]];c=[];(c<<(escape_char()|[[\\]];[["]]|[[^"]]))*;[["]];chars_to_string(c)""")
rule('int_value', r"""$"0x";hex_to_int(<hex_digit()+>) | dec_to_int(<[[0-9]]+>)""")
rule('bool_value', r"""$"true";true|$"false";false""")

# Character ranges
rule('char_range_char', r"""escape_char() | [[\\]]; [[\^\-\]]] | [[^\^\-\]]]""")
rule('char_range', r"""a=char_range_char(); b = a; ([[\-]]; b = char_range_char())?; Range(a, b)""")
rule('char_match', r"""$"["; invert=($"^";true|false); ranges=[]; (ranges<<char_range())*; $"]"; Character(ranges, invert)""")

# Pure match expressions.
rule('match_expr_atom', r"""(
    char_match()
    | $"("; S(); e=match_expr(); S(); $")"; e
    | $"<"; S(); e=match_expr(); S(); $">"; Slice(e)
    | MatchValue(Literal(string_value()))
    | Call(Get(ident()),[])
    )""")
rule('match_expr_repeat', r"""e=match_expr_atom();
    (e=(
        S();
        ( $"*"; Repeat(e, 0, 0)
        | $"+"; Repeat(e, 1, 0)
        | $"?"; Repeat(e, 0, 1))
    ))*; e""")
rule('match_expr_assign', r"""name=ident(); S(); ($"="; S(); Set(match_expr_repeat(), name)|$"<<"; S(); Append(match_expr_repeat(), name))
| match_expr_repeat()""")
rule('match_expr_sequence', r"""e=match_expr_assign(); (es =[e]; (S(); es<<match_expr_assign())+; e=Sequence(es))?; e""")
rule('match_expr_choice', r"""e=match_expr_sequence(); (es =[e]; (S(); $"|"; S(); es<<match_expr_sequence())+; e=Choice(es))?; e""")
rule('match_expr', r"""match_expr_choice()""")


rule('expr_atom', r"""(
    $"("; S(); e=expr(); S(); $")"; e
    | $"<"; S(); e=expr(); S(); $">"; Slice(e)
    | $"/"; S(); e=match_expr(); S(); $"/"; e
    | $"["; args = []; (S(); args << expr(); (S(); $","; S(); args << expr())*)?; S(); $"]"; List(args)
    | Literal(string_value())
    | Literal(int_value())
    | Literal(bool_value())
    | Get(ident())
    )""")
rule('expr_call', r"""e = expr_atom();
(
    S(); $"("; args=[];
    (
        S(); args<<expr();
        (
            S();
            $",";
            S();
            args<<expr()
        )*
    )?;
    S(); $")"; e=Call(e, args)
)*;
e""")
rule('expr_repeat', r"""e=expr_call();
    (e=(
        S();
        ( $"*"; Repeat(e, 0, 0)
        | $"+"; Repeat(e, 1, 0)
        | $"?"; Repeat(e, 0, 1))
    ))*; e""")
rule('expr_assign', r"""name=ident(); S(); ($"="; S(); Set(expr_repeat(), name)|$"<<"; S(); Append(expr_repeat(), name))
| expr_repeat()""")
rule('expr_sequence', r"""e=expr_assign(); (es=[e]; (S(); $";"; S(); es<<expr_assign())+; e=Sequence(es))?; e""")
rule('expr_choice', r"""e=expr_sequence(); (es=[e]; (S(); $"|"; S(); es<<expr_sequence())+; e=Choice(es))?; e""")
rule('expr', r"""expr_choice()""")
rule('type_ref', r"""$"[]";ref=type_ref();ListRef(ref)|NameRef(ident())""")
rule('rule_decl', r"""$"func"; S(); name=ident(); S(); $"("; S(); $")"; S(); $":"; S(); rt=type_ref(); S(); $"{"; S(); body=expr(); S(); $"}"; RuleDecl(name, rt, body)""")
rule('colon', r'$":"')
rule('field_decl', r"""name=ident(); S(); $":"; S(); FieldDecl(name, type_ref())""")

rule('struct_decl', r"""$"struct";
S(); name=ident();
S(); $"{";
fields=[];
(S(); fields<<field_decl())*;
S(); $"}";
StructDecl(name, fields)""")
rule('union_decl', r"""$"union";
S(); name=ident();
S(); $"=";
S(); refs=[type_ref()];
(S(); $"|"; S(); refs<<type_ref())*;
S(); $";";
UnionDecl(name, refs)""")
rule('extern_decl', r"""$"extern";
    S();
    name=ident();
    S(); $"(";
    params=[];
    (
        S(); params<<type_ref();
        (S(); $","; S(); params<<type_ref())*
    )?;
    S(); $")"; S(); colon(); S();
    rt=type_ref(); Extern(name, params, rt)""")
rule('file', r"""decls = []; (S(); decls << (rule_decl()|extern_decl()|struct_decl()|union_decl()))*; S(); File(decls)""")


class LocalSlot(object):
    def __init__(self, t):
        self.t = t


class SemanticPass(object):
    def __init__(self):
        self.scope_name = 'global'
        self.globals = {}
        self.locals = {}

    def resolveSlot(self, name):
        if name in self.locals:
            return self.locals[name]
        if name in self.globals:
            return self.globals[name]


class IndexGlobals(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.RuleDecl, model.Extern, model.StructDecl, model.UnionDecl)
    def visitRuleDecl(cls, node, semantic):
        if node.name in semantic.globals:
            raise Exception('Attempted to redefine "%s"' % node.name)
        semantic.globals[node.name] = node


class ResolveType(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.NameRef)
    def visitNameRef(cls, node, semantic):
        if node.name in set(['string', 'int', 'rune', 'void', 'bool']):
            return node.name
        elif node.name in semantic.globals:
            t = semantic.globals[node.name]
            assert isinstance(t, (model.StructDecl, model.UnionDecl)), t
        else:
            raise Exception('Unknown type "%s"' % node.name)

    @dispatch(model.ListRef)
    def visitListRef(cls, node, semantic):
        cls.visit(node.ref, semantic)


class CheckSignatures(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl)
    def visitStruct(cls, node, semantic):
        for f in node.fields:
            ResolveType.visit(f.t, semantic)

    @dispatch(model.UnionDecl)
    def visitUnionDecl(cls, node, semantic):
        for t in node.refs:
            ResolveType.visit(t, semantic)


    @dispatch(model.Extern)
    def visitExtern(cls, node, semantic):
        for p in node.params:
            ResolveType.visit(p, semantic)
        ResolveType.visit(node.rt, semantic)

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        ResolveType.visit(node.rt, semantic)


class CheckRules(object):
    __metaclass__ = TypeDispatcher

    @dispatch(model.File)
    def visitFile(cls, node, semantic):
        for decl in node.decls:
            cls.visit(decl, semantic)

    @dispatch(model.StructDecl, model.Extern, model.UnionDecl)
    def visitNop(cls, node, semantic):
        pass

    @dispatch(model.RuleDecl)
    def visitRuleDecl(cls, node, semantic):
        old_name = semantic.scope_name
        old_locals = semantic.locals
        semantic.scope_name = node.name
        semantic.locals = {}
        t = cls.visit(node.body, semantic)
        semantic.locals = old_locals

    @dispatch(Repeat)
    def visitRepeat(cls, node, semantic):
        cls.visit(node.expr, semantic)
        return 'void'

    @dispatch(Choice)
    def visitChoice(cls, node, semantic):
        for expr in node.children:
            cls.visit(expr, semantic)
        return 'void'

    @dispatch(Sequence)
    def visitSequence(cls, node, semantic):
        t = 'void'
        for expr in node.children:
            t = cls.visit(expr, semantic)
        return t

    @dispatch(Character)
    def visitCharacter(cls, node, semantic):
        return 'rune'

    @dispatch(MatchValue)
    def visitMatchValue(cls, node, semantic):
        return 'string' # HACK

    @dispatch(Slice)
    def visitSlice(cls, node, semantic):
        cls.visit(node.expr, semantic)
        return 'string'

    @dispatch(Call)
    def visitCall(cls, node, semantic):
        expr = cls.visit(node.expr, semantic)
        #if not isinstance(expr, (model.RuleDecl, model.Extern, model.StructDecl)):
        #    raise Exception('Cannot call %r in %s' % (type(expr), semantic.scope_name))
        for arg in node.args:
            cls.visit(arg, semantic)
        return '?'

    @dispatch(List)
    def visitList(cls, node, semantic):
        for arg in node.args:
            cls.visit(arg, semantic)
        return '[]?'

    @dispatch(Get)
    def visitGet(cls, node, semantic):
        slot = semantic.resolveSlot(node.name)
        if slot is None:
            raise Exception('Cannot resolve "%s" in %s' % (node.name, semantic.scope_name))

    @dispatch(Set)
    def visitSet(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        semantic.locals[node.name] = LocalSlot(t)
        return t

    @dispatch(Append)
    def visitAppend(cls, node, semantic):
        t = cls.visit(node.expr, semantic)
        slot = semantic.resolveSlot(node.name)
        if slot is None:
            raise Exception('Cannot resolve "%s" in %s' % (node.name, semantic.scope_name))
        return 'void'

    @dispatch(Literal)
    def visitLiteral(cls, node, semantic):
        return '?'


def compile(text):
    f = p.parse('file', text)
    semantic = SemanticPass()
    IndexGlobals.visit(f, semantic)
    CheckSignatures.visit(f, semantic)
    CheckRules.visit(f, semantic)
    return f
