from phase0 import sugar
from phase0.parser import *

import model

p = Parser()

def rule(name, body):
    p.rule(Rule(name, sugar.text_match(body)))

p.rule(Native('chr', unichr))
p.rule(Native('hex_to_int', lambda text: int(text, 16)))
p.rule(Native('dec_to_int', lambda text: int(text, 10)))
p.rule(Native('chars_to_string', lambda chars: ''.join(chars)))

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
    | $"("; e=match_expr(); $")"; e
    | $"<"; e=match_expr(); $">"; Slice(e)
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
    $"("; e=expr(); $")"; e
    | $"<"; e=expr(); $">"; Slice(e)
    | $"/"; e=match_expr(); $"/"; e
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
rule('type_ref', r"""ident()""")
rule('rule', r"""$"func"; S(); name=ident(); S(); $"("; S(); $")"; S(); $":"; S(); rt=type_ref(); S(); $"{"; S(); body=expr(); S(); $"}"; RuleDecl(name, rt, body)""")
