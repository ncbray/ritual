from interpreter import Parser, Rule, Native
import phase0.parser

import generate_python
import model
import semantic

p = Parser()

def rule(name, body):
    p.rule(Rule(name, phase0.parser.text_match(body)))

def halt():
    import pdb;pdb.set_trace()

p.rule(Native('chr', unichr))
p.rule(Native('hex_to_int', lambda text: int(text, 16)))
p.rule(Native('dec_to_int', lambda text: int(text, 10)))
p.rule(Native('chars_to_string', lambda chars: ''.join(chars)))
p.rule(Native('halt', halt))

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
    | MatchValue(StringLiteral(string_value()))
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
    | $"[]"; S(); t=type_ref(); S(); $"{"; args = []; (S(); args << expr(); (S(); $","; S(); args << expr())*)?; S(); $"}"; List(t, args)
    | StringLiteral(string_value())
    | IntLiteral(int_value())
    | BoolLiteral(bool_value())
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
rule('attribute', r"""Attribute(ident())""")
rule('attributes', r"""$"[";
attrs=[];
(attrs<<attribute(); (S(); $","; S(); attrs<<attribute())*)?;
$"]";
attrs""")
rule('optional_attributes', r"""attributes()|[]""")
rule('rule_decl', r"""attrs=optional_attributes(); S(); $"func"; S(); name=ident(); S(); $"("; S(); $")"; S(); $":"; S(); rt=type_ref(); S(); $"{"; S(); body=expr(); S(); $"}";
RuleDecl(name, rt, body, attrs)""")

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
    S(); $")"; S(); $":"; S();
    rt=type_ref(); ExternDecl(name, params, rt)""")
rule('file', r"""decls = []; (S(); decls << (rule_decl()|extern_decl()|struct_decl()|union_decl()))*; S(); File(decls)""")


def compile(name, text, out_dict):
    f = p.parse('file', text)
    semantic.process(f)
    src = generate_python.generate_source(f)
    generate_python.compile_source(name, src, out_dict)
