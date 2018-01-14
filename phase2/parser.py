import phase1.parser

src = r"""
extern chr(int):rune
extern hex_to_int(string):int
extern dec_to_int(string):int
extern chars_to_string([]rune):string

struct Range {
    lower:rune
    upper:rune
}
struct Character {
    ranges:[]Range
    invert:bool
}
struct Slice {
    expr:Matcher
}
struct Call {
    expr:Matcher
    args:[]Matcher
}
struct MatchValue {
    expr:Matcher
}
struct Literal {
    value:Intrinsic
}
struct List {
    args:[]Matcher
}
struct Get {
    name:string
}
struct Set {
    expr:Matcher
    name:string
}
struct Append {
    expr:Matcher
    name:string
}
struct Repeat {
    expr:Matcher
    min:int
    max:int
}
struct Sequence {
    children:[]Matcher
}
struct Choice {
    children:[]Matcher
}

union Intrinsic = string | int | bool;
union Matcher = Character | Slice | Call | MatchValue | Literal | List | Get | Set | Append | Repeat | Sequence | Choice;

func S():void {
    /([ \t\n\r]|"//"[^\n]*)*/
}
func hex_digit():rune {
    /[0-9a-fA-Z]/
}
func ident():string {
    </[a-zA-Z_][a-zA-Z_0-9]*/>
}
func escape_char():rune {
    /[\\]/;
    ( /[n]/; chr(0x0A)
    | /[r]/; chr(0x0D)
    | /[t]/; chr(0x09)
    | /[0]/; chr(0x00)
    | /[\\]/; chr(0x5C)
    | /[x]/; chr(hex_to_int(</hex_digit hex_digit/>))
    )
}
func string_value():string {
    /["]/;
    c = [];
    (
        c << /escape_char | [\\]["] | [^"]/
    )*;
    /["]/;
    chars_to_string(c)
}
func int_value():int {
    ( /"0x"/; hex_to_int(<hex_digit()+>)
    | dec_to_int(</[0-9]+/>)
    )
}
func bool_value():bool {
    ( /"true"/; true
    | /"false"/; false
    )
}
func char_range_char():rune {
    /escape_char | [\\][\^\-\\] | [^\^\-\\]/
}
func char_range():Range {
    a=char_range_char();
    ( /[\-]/; Range(a, char_range_char())
    | Range(a, a)
    )
}
func char_match():Character {
    /[[]/;
    invert=(/[\^]/;true|false);
    ranges = [];
    /[\]]/;
    Character(ranges, invert)
}
func match_expr_atom():Matcher {
    ( char_match()
    | /[(] S e=match_expr S [)]/; e
    | /[<] S e=match_expr S [>]/; Slice(e)
    | MatchValue(Literal(string_value()))
    | Call(Get(ident()),[])
    )
}
func match_expr_repeat():Matcher {
    e=match_expr_atom();
    (e=(
        S();
        ( /[*]/; Repeat(e, 0, 0)
        | /[+]/; Repeat(e, 1, 0)
        | /[?]/; Repeat(e, 0, 1))
    ))*;
    e
}
func match_expr_assign():Matcher {
    ( name=ident();
      S();
      ( /"="/; S(); Set(match_expr_repeat(), name)
      | /"<<"/; S(); Append(match_expr_repeat(), name)
      )
    | match_expr_repeat())
}
func match_expr_sequence():Matcher {
    e=match_expr_assign();
    (
        es=[e];
        (
            S(); es<<match_expr_assign()
        )+;
        e=Sequence(es)
    )?;
    e
}
func match_expr_choice():Matcher {
    e=match_expr_sequence();
    (
        es=[e];
        (/S "|" S/; es<<match_expr_sequence())+;
        e=Choice(es)
    )?;
    e
}
func match_expr():Matcher {
    match_expr_choice()
}
"""

f = phase1.parser.compile(src)
#print f
