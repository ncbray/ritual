import phase1.parser

src = r"""
extern chr(i:int):rune
extern chars_to_string(chars:[]rune):string
extern hex_to_int(text:string):int
extern dec_to_int(text:string):int

struct Token {
    loc:location
    text:string
}
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
struct Location {
}
struct StringLiteral {
    value:string
}
struct RuneLiteral {
    value:rune
}
struct IntLiteral {
    value:int
}
struct BoolLiteral {
    value:bool
}
struct StructLiteral {
    t:NameRef
    args:[]Matcher
}
struct ListLiteral {
    t:TypeRef
    args:[]Matcher
}
struct Get {
    name:Token
}
struct Set {
    expr:Matcher
    name:Token
}
struct Append {
    expr:Matcher
    name:Token
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
struct NameRef {
    name:Token
}
struct ListRef {
    ref:TypeRef
}
struct Param {
    name:Token
    t:TypeRef
}
struct RuleDecl {
    name:Token
    params:[]Param
    rt:TypeRef
    body:Matcher
    attrs:[]Attribute
}
struct ExternDecl {
    name:Token
    params:[]Param
    rt:TypeRef
}
struct FieldDecl {
    name:Token
    t:TypeRef
}
struct StructDecl {
    name:Token
    fields:[]FieldDecl
}
struct UnionDecl {
    name:Token
    refs:[]TypeRef
}
struct File {
    decls:[]Decl
}
struct Attribute {
    name:Token
}
union TypeRef = NameRef | ListRef;
union Matcher = Character | Slice | Call | MatchValue | Location | StringLiteral | RuneLiteral | IntLiteral | BoolLiteral | StructLiteral | ListLiteral | Get | Set | Append | Repeat | Sequence | Choice;
union Decl = RuleDecl | ExternDecl | StructDecl | UnionDecl;

func S():void {
    /([ \t\n\r]|"//"[^\n]*)*/
}
func hex_digit():rune {
    /[0-9a-fA-Z]/
}
func ident():Token {
    Token{loc(), </[a-zA-Z_][a-zA-Z_0-9]*/>}
}
func escape_char():rune {
    /[\\]/;
    ( /[n]/; chr(0x0A)
    | /[r]/; chr(0x0D)
    | /[t]/; chr(0x09)
    | /[0]/; chr(0x00)
    | /[\\]/; chr(0x5C)
    | /[x]/; chr(hex_to_int(</hex_digit hex_digit/>))
    | /[u][{] digits=<hex_digit+> [}]/; chr(hex_to_int(digits))
    )
}
func string_value():string {
    /["]/;
    c = []rune{};
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
    /escape_char | [\\] [\^\-\\\]] | [^\^\-\\\]]/
}
func char_range():Range {
    a=char_range_char();
    ( /[\-]/; Range{a, char_range_char()}
    | Range{a, a}
    )
}
func char_match():Character {
    /[[]/;
    invert = (/[\^]/;true|false);
    ranges = []Range{};
    (ranges<<char_range())*;
    /[\]]/;
    Character{ranges, invert}
}
func match_expr_atom():Matcher {
    ( char_match()
    | /[(] S e=match_expr S [)]/; e
    | /[<] S e=match_expr S [>]/; Slice{e}
    | MatchValue{StringLiteral{string_value()}}
    | /"loc"/; Location{}
    | Call{Get{ident()},[]Matcher{}}
    )
}
func match_expr_repeat():Matcher {
    e=match_expr_atom();
    (e=(
        S();
        ( /[*]/; Repeat{e, 0, 0}
        | /[+]/; Repeat{e, 1, 0}
        | /[?]/; Repeat{e, 0, 1})
    ))*;
    e
}
func match_expr_assign():Matcher {
    ( name=ident();
      S();
      ( /"="/; S(); Set{match_expr_repeat(), name}
      | /"<<"/; S(); Append{match_expr_repeat(), name}
      )
    | match_expr_repeat())
}
func match_expr_sequence():Matcher {
    e=match_expr_assign();
    (
        es = []Matcher{e};
        (
            S(); es<<match_expr_assign()
        )+;
        e=Sequence{es}
    )?;
    e
}
func match_expr_choice():Matcher {
    e=match_expr_sequence();
    (
        es = []Matcher{e};
        (/S "|" S/; es<<match_expr_sequence())+;
        e=Choice{es}
    )?;
    e
}
func match_expr():Matcher {
    match_expr_choice()
}
func struct_literal_args():[]Matcher {
    args = []Matcher{};
    (
        args << expr();
        (/S "," S/; args << expr())*
    )?;
    args
}
func struct_literal():StructLiteral {
    /t=name_ref S "{" S args=struct_literal_args S "}"/;
    StructLiteral{t, args}
}
func expr_atom():Matcher {
    ( /"(" S e=expr S ")"/; e
    | /"<" S e=expr S ">"/; Slice{e}
    | /"/" S e=match_expr S "/"/; e
    | /"[]" S t=type_ref S "{"/; args = []Matcher{}; (S(); args << expr(); (/S "," S/; args << expr())*)?; /S "}"/; ListLiteral{t, args}
    | struct_literal()
    | StringLiteral{string_value()}
    | IntLiteral{int_value()}
    | BoolLiteral{bool_value()}
    | /"loc" S "(" S ")"/; Location{}
    | Get{ident()}
    )
}
func expr_call():Matcher {
    e = expr_atom();
    (
        /S "("/;
        args = []Matcher{};
        (
            S(); args<<expr();
            (
                /S "," S/;
                args<<expr()
            )*
        )?;
        /S ")"/;
        e=Call{e, args}
    )*;
    e
}
func expr_repeat():Matcher {
    e=expr_call();
    (
        e=(
            S();
            ( /"*"/; Repeat{e, 0, 0}
            | /"+"/; Repeat{e, 1, 0}
            | /"?"/; Repeat{e, 0, 1}
            )
        )
    )*;
    e
}
func expr_assign():Matcher {
    name=ident();
    S();
    (/"=" S/; Set{expr_repeat(), name}
    |/"<<" S/; Append{expr_repeat(), name}
    )
    | expr_repeat()
}
func expr_sequence():Matcher {
    e=expr_assign();
    (
        es = []Matcher{e};
        (
            /S ";" S/;
            es<<expr_assign()
        )+;
        e=Sequence{es}
    )?;
    e
}
func expr_choice():Matcher {
    e=expr_sequence();
    (
        es = []Matcher{e};
        (
            /S "|" S/;
            es<<expr_sequence()
        )+;
        e=Choice{es}
    )?;
    e
}
func expr():Matcher {
    expr_choice()
}
func list_ref():ListRef {
    /"[]" ref=type_ref/; ListRef{ref}
}
func name_ref():NameRef {
    NameRef{ident()}
}
func type_ref():TypeRef {
    list_ref() | name_ref()
}
func attribute():Attribute {
    Attribute{ident()}
}
func attributes():[]Attribute {
    /"["/;
    attrs = []Attribute{};
    (
        attrs<<attribute();
        (/S "," S/; attrs<<attribute())*
    )?;
    /"]"/;
    attrs
}
func optional_attributes():[]Attribute {
    attributes() | []Attribute{}
}
func param():Param {
    /name=ident S ":" S t=type_ref/;
    Param{name, t}
}
func param_list():[]Param {
    /"("/;
    params = []Param{};
    (
        S(); params<<param();
        (/S "," S/; params<<param())*
    )?;
    /S ")"/;
    params
}
func rule_decl():RuleDecl {
    attrs=optional_attributes(); S();
    /"func" S name=ident S params=param_list S ":" S rt=type_ref S "{" S body=expr S "}"/;
    RuleDecl{name, params, rt, body, attrs}
}
func field_decl():FieldDecl {
    name=ident(); /S ":" S/; FieldDecl{name, type_ref()}
}
func struct_decl():StructDecl {
    /"struct" S name=ident S "{"/;
    fields = []FieldDecl{};
    (S(); fields<<field_decl())*;
    /S "}"/;
    StructDecl{name, fields}
}
func union_decl():UnionDecl {
    /"union" S name=ident S "=" S/;
    refs = []TypeRef{type_ref()};
    (/S "|" S/; refs<<type_ref())*;
    /S ";"/;
    UnionDecl{name, refs}
}
func extern_decl():ExternDecl {
    /"extern" S name=ident S params=param_list S ":" S rt=type_ref/;
    ExternDecl{name, params, rt}
}
func decl():Decl {
    rule_decl()|struct_decl()|extern_decl()|union_decl()
}
[export]
func file():File {
    decls = []Decl{};
    (S(); decls<<decl())*;
    S();
    File{decls}
}
"""

def setup(src):
    phase1.parser.compile('phase2_gen', src, globals())
    p = buildParser(
        chr=unichr,
        chars_to_string=lambda chars: ''.join(chars),
        hex_to_int=lambda text: int(text, 16),
        dec_to_int=lambda text: int(text, 10),
    )
    p.parse('file', src)
    return p

p = setup(src)
