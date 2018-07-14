import unittest

from ritual.interpreter.testutil import ParserTestCase

from . import model
from . import parser


def simpleCompile(text):
    d = {}
    parser.compile('test', text, d)
    return d['buildParser']()


class TestParser(ParserTestCase):
    def setUp(self):
        self.parser = parser.p

    def test_ident(self):
        for ident in ['FooBar', 'foo_bar', '_', 'f123']:
            self.p_ok('ident', ident, model.Token(0, ident))
        for ident in ['123', '', '$']:
            self.p_fail('ident', ident)

    def test_escape_char(self):
        cases = [
            (r'\n', '\n'),
            (r'\r', '\r'),
            (r'\t', '\t'),
            (r'\0', '\0'),
            (r'\x00', '\0'),
            (r'\\', '\\'),
            (r'\u{2014}', u'\u2014'),
        ]
        for text, result in cases:
            self.p_ok('escape_char', text, result)

    def test_string(self):
        cases = [
            (r'""', ''),
            (r'"abc"', 'abc'),
            (r'"\""', '"'),
            (r'"\n"', '\n'),
        ]
        for text, result in cases:
            self.p_ok('string_value', text, result)

    def test_int(self):
        cases = [
            (r'0', 0),
            (r'1', 1),
            (r'123456', 123456),
            (r'0xff', 0xff),
        ]
        for text, result in cases:
            self.p_ok('int_value', text, result)

    def test_char_match(self):
        cases = [
            (r'[]', False, 0),
            (r'[^]', True, 0),
            (r'[a]', False, 1),
            (r'[a-z]', False, 1),
            (r'[a-zA-Z_]', False, 3),
            (r'[^\n]', True, 1),
        ]
        for text, inv, num in cases:
            m = self.p_ok('char_match', text)
            self.assertEqual(m.invert, inv)
            self.assertEqual(len(m.ranges), num)

    def test_match_expr(self):
        self.p_ok('match_expr', r'result=<("foo"|"bar"|other)+>')

    def test_expr(self):
        self.p_ok('expr', r'a(); b(x) | c(x, x); d(x , x , x)')

    def test_rule(self):
        self.p_ok('rule_decl', r'func foo():string {/"foo"/}')


class TestAlternateParsers(ParserTestCase):

    def test_func_params(self):
        self.parser = simpleCompile(r"""
[export]
func bracket(s:string):string {
    <$"["; $s; $"]">
}
[export]
func wrap():string {
  bracket("wrap")
}
""")
        self.p_ok('bracket', '[foo]', args=['foo'])
        self.p_fail('bracket', '[foo]', args=['bar'])
        self.p_ok('bracket', '[\0]', args=['\0'])
        self.p_ok('wrap', '[wrap]')

    def test_lookahead(self):
        self.parser = simpleCompile(r"""
[export]
func keyword(s:string):void {
    $s; !/[a-zA-Z_0-9]/
}
[export]
func main(s:string):string {
  keyword(s); /[ ]* <[^]*>/
}
""")

        self.p_ok('main', 'foo bar', args=['foo'], value='bar')
        self.p_fail('main', 'foobar', args=['foo'])
        self.p_ok('main', 'foo{}', args=['foo'], value='{}')
