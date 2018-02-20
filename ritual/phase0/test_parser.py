import unittest
from ritual.interpreter import Parser, Rule, Native, Param
from ritual.interpreter.testutil import ParserTestCase
import parser


class TestParser(ParserTestCase):
    def test_char(self):
        p = Parser()
        p.rule(Rule('one', [], parser.text_match(r'[[0-9]]')))
        p.rule(Rule('two', [], parser.text_match(r'[[^0-9]]')))
        p.rule(Rule('three', [], parser.text_match(r'[[\t\n]]')))
        self.parser = p

        self.p_fail("one", "c")
        self.p_ok("one", "3")

        self.p_ok("two", "c")
        self.p_fail("two", "3")

        self.p_ok("three", "\t")
        self.p_ok("three", "\n")
        self.p_fail("three", r"\n")

    def test_digit_plus(self):
        p = Parser()
        p.rule(Rule('digits', [], parser.text_match(r'[[0-9]]+')))
        self.parser = p

        self.p_fail("digits", "")
        self.p_ok("digits", "1")
        self.p_ok("digits", "12")
        self.p_ok("digits", "1234567890")

    def test_digit_star(self):
        p = Parser()
        p.rule(Rule('digits', [], parser.text_match(r'[[0-9]]*')))
        self.parser = p

        self.p_ok("digits", "")
        self.p_ok("digits", "1")
        self.p_ok("digits", "12")
        self.p_ok("digits", "1234567890")

    def test_digit_question(self):
        p = Parser()
        p.rule(Rule('digits', [], parser.text_match(r'[[0-9]]?')))
        self.parser = p

        self.p_ok("digits", "")
        self.p_ok("digits", "1")
        self.p_fail("digits", "12")

    def test_sequence(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'[[a]];[[b]]+')))
        self.parser = p

        self.p_fail("test", "a")
        self.p_ok("test", "ab")
        self.p_fail("test", "aa")
        self.p_fail("test", "aba")
        self.p_ok("test", "abb")

    def test_grouping(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'([[a]];[[b]])+')))
        self.parser = p

        self.p_fail("test", "a")
        self.p_ok("test", "ab")
        self.p_fail("test", "aa")
        self.p_fail("test", "aba")
        self.p_fail("test", "abb")
        self.p_ok("test", "abab")
        self.p_ok("test", "ababab")

    def test_string(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'$"foo"')))
        self.parser = p

        self.p_ok("test", "foo")
        self.p_fail("test", "fo")
        self.p_fail("test", "fooo")
        self.p_fail("test", "bar")

    def test_choice(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'$"foo" | $"bar"')))
        self.parser = p

        self.p_ok("test", "foo", "foo")
        self.p_ok("test", "bar", "bar")
        self.p_fail("test", "boo")
        self.p_fail("test", "baz")

    def test_assign(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'"("; c = [[a-zA-Z_]]; ")"; c')))
        self.parser = p

    def test_list_literal(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'["a", "b", "c"]')))
        self.parser = p

        self.p_ok("test", "", ['a', 'b', 'c'])

    def test_list_append(self):
        p = Parser()
        p.rule(Rule('test', [], parser.text_match(r'e = []; e << "a"; e << "b"; e << "c"; e')))
        self.parser = p

        self.p_ok("test", "", ['a', 'b', 'c'])

    def test_call(self):
        p = Parser()
        p.rule(Native('add', [Param('a'), Param('b')], lambda a, b: a + b))
        p.rule(Rule('test', [], parser.text_match(r'add(1, 2)')))
        self.parser = p

        self.p_ok("test", "", 3)
