from interpreter import *
import unittest


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
