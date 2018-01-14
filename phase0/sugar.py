from parser import *

def punc(*chars):
    return Character([Range(c, c) for c in chars], False)

def not_punc(*chars):
    return Character([Range(c, c) for c in chars], True)

def tok(text):
    return MatchValue(Literal(text))

def optional(e):
    return Choice([e, Sequence([])])

p = Parser()

p.rule(Native('chars_to_string', lambda chars: ''.join(chars)))
p.rule(Native('string_to_int', lambda text: int(text, 0)))

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

p.rule(Rule('S',
    Repeat(punc(' ', '\t', '\n', '\r'), 0, 0)
))
p.rule(Rule('esc_char',
    punc('\\') & (
        punc('n') & Literal('\n')
        | punc('t') & Literal('\t')
        | punc('r') & Literal('\r')
        | Slice(Any())
    )
))
p.rule(Rule('c',
    Get('esc_char')() | Slice(Character([Range(']', ']'), Range('-', '-'), Range('^', '^')], True))
))
p.rule(Rule('r',
    Set(Get('c')(), 'a') & (punc('-') & Get('Range')(Get('a'), Get('c')()) | Get('Range')(Get('a'), Get('a')))
))
p.rule(Rule('char',
    tok('[[') & Set(Literal(False), 'inv') & Set(List([]), 'ranges') & optional(punc('^') & Set(Literal(True), 'inv')) & Repeat(Append(Get('r')(), 'ranges'), 0, 0) & tok(']]') & Get('Character')(Get('ranges'), Get('inv'))
))
p.rule(Rule('string_literal',
    punc('"') & Set(List([]), 'chars') & Repeat(Append(Get('esc_char')() | Slice(not_punc('"')), 'chars'), 0, 0) & punc('"') & Get('Literal')(Get('chars_to_string')(Get('chars')))
))
p.rule(Rule('boolean_literal',
    tok('true') & Get('Literal')(Literal(True)) | tok('false') & Get('Literal')(Literal(False))
))
p.rule(Rule('int_literal',
    Get('Literal')(
        Get('string_to_int')(
            Slice(
                MatchValue(Literal("0x"))
                & Repeat(Character([Range('0', '9'), Range('a', 'f'), Range('A', 'F')], False), 1, 0)
                | Repeat(Character([Range('0', '9')], False), 1, 0)
            )
        )
    )
))
p.rule(Rule('list_literal',
    punc('[') & Set(List([]), 'es') &
        (Get('S')() & Append(Get('expr')(), 'es') & Repeat(Get('S')() & punc(',') & Get('S')() & Append(Get('expr')(), 'es'), 0, 0)
        | Sequence([])
    ) & Get('S')() & punc(']') & Get('List')(Get('es'))
))
p.rule(Rule('ident',
    Slice(Repeat(Character([Range('a', 'z'), Range('A', 'Z'), Range('_', '_')], False), 1, 0))
))
p.rule(Rule('atom',
    punc('(') & Get('S')() & Set(Get('expr')(), 'e') & Get('S')() & punc(')') & Get('e')
    | punc('<') & Get('S')() & Set(Get('expr')(), 'e') & Get('S')() & punc('>') & Get('Slice')(Get('e'))
    | punc('$') & Get('S')() & Get('MatchValue')(Get('atom')())
    | Get('char')()
    | punc('.') & Get('Any')()
    | Get('list_literal')()
    | Get('string_literal')()
    | Get('boolean_literal')()
    | Get('int_literal')()
    | Get('Get')(Get('ident')())
))
p.rule(Rule('call',
    Set(Get('atom')(), 'e')
    & Repeat(Set(
        punc('(')
        & Set(List([]), 'args')
        & (
            Get('S')() & Append(Get('expr')(), 'args')
            & Repeat(Get('S')() & punc(',') & Get('S')() & Append(Get('expr')(), 'args'), 0, 0)
            | Sequence([])
        )
        & Get('S')() & punc(')')
        & Get('Call')(Get('e'), Get('args')),
    'e'), 0, 0)
    & Get('e')
))
p.rule(Rule('repeat',
    Set(Get('call')(), 'e')
    & ( Get('S')() &
        ( punc('*') & Get('Repeat')(Get('e'), Literal(0), Literal(0))
        | punc('+') & Get('Repeat')(Get('e'), Literal(1), Literal(0))
        | punc('?') & Get('Repeat')(Get('e'), Literal(0), Literal(1)) # TODO implement as choice?
        # TODO {m,n}
        )
    | Get('e')
    )
))
p.rule(Rule('assign',
    (Set(Get('ident')(), 'name') & Get('S')() &
        ( punc('=') & Get('S')() & Get('Set')(Get('repeat')(), Get('name'))
        | tok('<<') & Get('S')() & Get('Append')(Get('repeat')(), Get('name'))
        )
    | Get('repeat')()
    )
))

p.rule(Rule('sequence',
    Set(Get('assign')(), 'e')
    & (
        Set(List([Get('e')]), 'es')
        & Repeat(Append(Get('S')() & punc(';') & Get('S')() & Get('assign')(), 'es'), 1, 0)
        & Get('Sequence')(Get('es'))
    | Get('e')
    )
))
p.rule(Rule('choice',
    Set(Get('sequence')(), 'e')
    & (
        Set(List([Get('e')]), 'es')
        & Repeat(Append(Get('S')() & punc('|') & Get('S')() &Get('sequence')(), 'es'), 1, 0)
        & Get('Choice')(Get('es'))
    | Get('e')
    )
))

p.rule(Rule('expr',
    Get('choice')()
))


def text_match(text):
    return p.parse('expr', text)
