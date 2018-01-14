import unittest

from parser import *

class TestParser(unittest.TestCase):
    def test_ident(self):
        for ident in ["FooBar", "foo_bar", "_", 'f123']:
            self.assertEqual(p.parse("ident", ident), ident)
        for ident in ['123', '', '$']:
            with self.assertRaises(ParseFailed):
                p.parse('ident', ident)

    def test_escape_char(self):
        cases = [
            (r'\n', '\n'),
            (r'\r', '\r'),
            (r'\t', '\t'),
            (r'\0', '\0'),
            (r'\x00', '\0'),
            (r'\\', '\\'),
        ]
        for text, result in cases:
            self.assertEqual(p.parse("escape_char", text), result)

    def test_string(self):
        cases = [
            (r'""', ''),
            (r'"abc"', 'abc'),
            (r'"\""', '"'),
            (r'"\n"', '\n'),
        ]
        for text, result in cases:
            self.assertEqual(p.parse("string_value", text), result)

    def test_int(self):
        cases = [
            (r'0', 0),
            (r'1', 1),
            (r'123456', 123456),
            (r'0xff', 0xff),
        ]
        for text, result in cases:
            self.assertEqual(p.parse("int_value", text), result)

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
            m = p.parse("char_match", text)
            self.assertEqual(m.invert, inv)
            self.assertEqual(len(m.ranges), num)

    def test_match_expr(self):
        m = p.parse("match_expr", r'result=<("foo"|"bar"|other)+>')
        #print m

    def test_expr(self):
        m = p.parse("expr", r'a(); b(x) | c(x, x); d(x , x , x)')
        #print m
