import unittest
from interpreter import Parser, Rule, ParseFailed, Native, Param
import parser


class TestParser(unittest.TestCase):
    def test_char(self):
        p = Parser()
        p.rule(Rule('one', parser.text_match(r'[[0-9]]')))
        p.rule(Rule('two', parser.text_match(r'[[^0-9]]')))
        p.rule(Rule('three', parser.text_match(r'[[\t\n]]')))

        with self.assertRaises(ParseFailed):
            p.parse("one", "c")
        p.parse("one", "3")

        p.parse("two", "c")
        with self.assertRaises(ParseFailed):
            p.parse("two", "3")

        p.parse("three", "\t")
        p.parse("three", "\n")
        with self.assertRaises(ParseFailed):
            p.parse("three", r"\n")

    def test_digit_plus(self):
        p = Parser()
        p.rule(Rule('digits', parser.text_match(r'[[0-9]]+')))
        with self.assertRaises(ParseFailed):
            p.parse("digits", "")
        p.parse("digits", "1")
        p.parse("digits", "12")
        p.parse("digits", "1234567890")

    def test_digit_star(self):
        p = Parser()
        p.rule(Rule('digits', parser.text_match(r'[[0-9]]*')))
        p.parse("digits", "")
        p.parse("digits", "1")
        p.parse("digits", "12")
        p.parse("digits", "1234567890")

    def test_digit_question(self):
        p = Parser()
        p.rule(Rule('digits', parser.text_match(r'[[0-9]]?')))
        p.parse("digits", "")
        p.parse("digits", "1")
        with self.assertRaises(ParseFailed):
            p.parse("digits", "12")

    def test_sequence(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'[[a]];[[b]]+')))
        with self.assertRaises(ParseFailed):
            p.parse("test", "a")
        p.parse("test", "ab")
        with self.assertRaises(ParseFailed):
            p.parse("test", "aa")
        with self.assertRaises(ParseFailed):
            p.parse("test", "aba")
        p.parse("test", "abb")

    def test_grouping(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'([[a]];[[b]])+')))
        with self.assertRaises(ParseFailed):
            p.parse("test", "a")
        p.parse("test", "ab")
        with self.assertRaises(ParseFailed):
            p.parse("test", "aa")
        with self.assertRaises(ParseFailed):
            p.parse("test", "aba")
        with self.assertRaises(ParseFailed):
            p.parse("test", "abb")
        p.parse("test", "abab")
        p.parse("test", "ababab")

    def test_string(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'$"foo"')))
        p.parse("test", "foo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "fo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "fooo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "bar")

    def test_choice(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'$"foo" | $"bar"')))
        self.assertEqual(p.parse("test", "foo"), "foo")
        self.assertEqual(p.parse("test", "bar"), "bar")
        with self.assertRaises(ParseFailed):
            p.parse("test", "boo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "baz")

    def test_assign(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'"("; c = [[a-zA-Z_]]; ")"; c')))

    def test_list_literal(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'["a", "b", "c"]')))
        self.assertEqual(p.parse("test", ""), ['a', 'b', 'c'])

    def test_list_append(self):
        p = Parser()
        p.rule(Rule('test', parser.text_match(r'e = []; e << "a"; e << "b"; e << "c"; e')))
        self.assertEqual(p.parse("test", ""), ['a', 'b', 'c'])

    def test_call(self):
        p = Parser()
        p.rule(Native('add', [Param('a'), Param('b')], lambda a, b: a + b))
        p.rule(Rule('test', parser.text_match(r'add(1, 2)')))
        self.assertEqual(p.parse("test", ""), 3)
