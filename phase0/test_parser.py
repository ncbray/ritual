#!/usr/bin/python

import unittest

from parser import *
import sugar

class TestSimpleParser(unittest.TestCase):
    def setUp(self):
        p = Parser()
        p.rule(Rule("t", MatchValue(Literal("true"))))
        p.rule(Rule("f", MatchValue(Literal("fals")) & MatchValue(Literal("e"))))
        p.rule(Rule("b", Get("t")() | Get("f")()))
        p.rule(Rule("num", Character([Range('0', '9')], False)))
        p.rule(Rule("not_num", Character([Range('0', '9')], True)))
        p.rule(Rule("letter", Character([Range('a', 'z'), Range('A', 'Z')], False)))
        p.rule(Rule("word", Repeat(Get("letter")(), 1, 0)))
        p.rule(Rule("short_word", Repeat(Get("letter")(), 1, 3)))
        p.rule(Rule("maybe_word", Repeat(Get("letter")(), 0, 0)))

        self.parser = p

    def test_t_match(self):
        self.parser.parse("t", "true")
        with self.assertRaises(ParseFailed):
            self.parser.parse("t", "true ")
        with self.assertRaises(ParseFailed):
            self.parser.parse("t", "false")
        with self.assertRaises(ParseFailed):
            self.parser.parse("t", "")
        with self.assertRaises(ParseFailed):
            self.parser.parse("t", "tru")

    def test_b(self):
        self.parser.parse("b", "true")
        self.parser.parse("b", "false")
        with self.assertRaises(ParseFailed):
            self.parser.parse("b", "maybe")

    def test_num(self):
        self.parser.parse("num", "0")
        self.parser.parse("num", "5")
        self.parser.parse("num", "9")
        with self.assertRaises(ParseFailed):
            self.parser.parse("num", "")
        with self.assertRaises(ParseFailed):
            self.parser.parse("num", "d")
        with self.assertRaises(ParseFailed):
            self.parser.parse("num", "!")

    def test_not_num(self):
        self.parser.parse("not_num", "d")
        self.parser.parse("not_num", "!")
        with self.assertRaises(ParseFailed):
            self.parser.parse("not_num", "")
        with self.assertRaises(ParseFailed):
            self.parser.parse("not_num", "0")
        with self.assertRaises(ParseFailed):
            self.parser.parse("not_num", "5")
        with self.assertRaises(ParseFailed):
            self.parser.parse("not_num", "9")

    def test_letter(self):
        self.parser.parse("letter", "a")
        self.parser.parse("letter", "g")
        self.parser.parse("letter", "z")
        self.parser.parse("letter", "A")
        self.parser.parse("letter", "G")
        self.parser.parse("letter", "Z")
        with self.assertRaises(ParseFailed):
            self.parser.parse("letter", "")
        with self.assertRaises(ParseFailed):
            self.parser.parse("letter", "7")
        with self.assertRaises(ParseFailed):
            self.parser.parse("letter", "!")

    def test_word(self):
        with self.assertRaises(ParseFailed):
            self.parser.parse("word", "")
        self.parser.parse("word", "a")
        self.parser.parse("word", "cat")
        self.parser.parse("word", "aardvark")

        with self.assertRaises(ParseFailed):
            self.parser.parse("short_word", "")
        self.parser.parse("short_word", "a")
        self.parser.parse("short_word", "cat")
        with self.assertRaises(ParseFailed):
            self.parser.parse("short_word", "aardvark")

        self.parser.parse("maybe_word", "")
        self.parser.parse("maybe_word", "aardvark")


class TestParserValues(unittest.TestCase):
    def setUp(self):
        p = Parser()
        p.rule(Rule("num", Slice(Character([Range('0', '9')], False))))
        p.rule(Rule("three", Set(List([]), "l") & Append(Get("num")(), "l") & Append(Get("num")(), "l") & Append(Get("num")(), "l") & Get("l")))

        self.parser = p

    def test_three(self):
        self.assertEqual(["1", "2", "3"], self.parser.parse("three", "123"))
        with self.assertRaises(ParseFailed):
            self.parser.parse("three", "12b")


class TestSugar(unittest.TestCase):
    def test_char(self):
        p = Parser()
        p.rule(Rule('one', sugar.text_match(r'[[0-9]]')))
        p.rule(Rule('two', sugar.text_match(r'[[^0-9]]')))
        p.rule(Rule('three', sugar.text_match(r'[[\t\n]]')))

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
        p.rule(Rule('digits', sugar.text_match(r'[[0-9]]+')))
        with self.assertRaises(ParseFailed):
            p.parse("digits", "")
        p.parse("digits", "1")
        p.parse("digits", "12")
        p.parse("digits", "1234567890")

    def test_digit_star(self):
        p = Parser()
        p.rule(Rule('digits', sugar.text_match(r'[[0-9]]*')))
        p.parse("digits", "")
        p.parse("digits", "1")
        p.parse("digits", "12")
        p.parse("digits", "1234567890")

    def test_digit_question(self):
        p = Parser()
        p.rule(Rule('digits', sugar.text_match(r'[[0-9]]?')))
        p.parse("digits", "")
        p.parse("digits", "1")
        with self.assertRaises(ParseFailed):
            p.parse("digits", "12")

    def test_sequence(self):
        p = Parser()
        p.rule(Rule('test', sugar.text_match(r'[[a]];[[b]]+')))
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
        p.rule(Rule('test', sugar.text_match(r'([[a]];[[b]])+')))
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
        p.rule(Rule('test', sugar.text_match(r'$"foo"')))
        p.parse("test", "foo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "fo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "fooo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "bar")

    def test_choice(self):
        p = Parser()
        p.rule(Rule('test', sugar.text_match(r'$"foo" | $"bar"')))
        self.assertEqual(p.parse("test", "foo"), "foo")
        self.assertEqual(p.parse("test", "bar"), "bar")
        with self.assertRaises(ParseFailed):
            p.parse("test", "boo")
        with self.assertRaises(ParseFailed):
            p.parse("test", "baz")

    def test_assign(self):
        p = Parser()
        p.rule(Rule('test', sugar.text_match(r'"("; c = [[a-zA-Z_]]; ")"; c')))

    def test_list_literal(self):
        p = Parser()
        p.rule(Rule('test', sugar.text_match(r'["a", "b", "c"]')))
        self.assertEqual(p.parse("test", ""), ['a', 'b', 'c'])

    def test_list_append(self):
        p = Parser()
        p.rule(Rule('test', sugar.text_match(r'e = []; e << "a"; e << "b"; e << "c"; e')))
        self.assertEqual(p.parse("test", ""), ['a', 'b', 'c'])

    def test_call(self):
        p = Parser()
        p.rule(Native('add', lambda a, b: a + b))
        p.rule(Rule('test', sugar.text_match(r'add(1, 2)')))
        self.assertEqual(p.parse("test", ""), 3)

if __name__ == '__main__':
    unittest.main()
