from interpreter import *
import unittest


class TestSimpleParser(unittest.TestCase):
    def setUp(self):
        p = Parser()
        p.rule(Rule("t", [], MatchValue(Literal("true"))))
        p.rule(Rule("f", [], MatchValue(Literal("fals")) & MatchValue(Literal("e"))))
        p.rule(Rule("b", [], Get("t")() | Get("f")()))
        p.rule(Rule("num", [], Character([Range('0', '9')], False)))
        p.rule(Rule("not_num", [], Character([Range('0', '9')], True)))
        p.rule(Rule("letter", [], Character([Range('a', 'z'), Range('A', 'Z')], False)))
        p.rule(Rule("word", [], Repeat(Get("letter")(), 1, 0)))
        p.rule(Rule("short_word", [], Repeat(Get("letter")(), 1, 3)))
        p.rule(Rule("maybe_word", [], Repeat(Get("letter")(), 0, 0)))

        self.parser = p

    def p(self, name, text):
        return self.parser.parse(name, [], text)

    def test_t_match(self):
        self.p("t", "true")
        with self.assertRaises(ParseFailed):
            self.p("t", "true ")
        with self.assertRaises(ParseFailed):
            self.p("t", "false")
        with self.assertRaises(ParseFailed):
            self.p("t", "")
        with self.assertRaises(ParseFailed):
            self.p("t", "tru")

    def test_b(self):
        self.p("b", "true")
        self.p("b", "false")
        with self.assertRaises(ParseFailed):
            self.p("b", "maybe")

    def test_num(self):
        self.p("num", "0")
        self.p("num", "5")
        self.p("num", "9")
        with self.assertRaises(ParseFailed):
            self.p("num", "")
        with self.assertRaises(ParseFailed):
            self.p("num", "d")
        with self.assertRaises(ParseFailed):
            self.p("num", "!")

    def test_not_num(self):
        self.p("not_num", "d")
        self.p("not_num", "!")
        with self.assertRaises(ParseFailed):
            self.p("not_num", "")
        with self.assertRaises(ParseFailed):
            self.p("not_num", "0")
        with self.assertRaises(ParseFailed):
            self.p("not_num", "5")
        with self.assertRaises(ParseFailed):
            self.p("not_num", "9")

    def test_letter(self):
        self.p("letter", "a")
        self.p("letter", "g")
        self.p("letter", "z")
        self.p("letter", "A")
        self.p("letter", "G")
        self.p("letter", "Z")
        with self.assertRaises(ParseFailed):
            self.p("letter", "")
        with self.assertRaises(ParseFailed):
            self.p("letter", "7")
        with self.assertRaises(ParseFailed):
            self.p("letter", "!")

    def test_word(self):
        with self.assertRaises(ParseFailed):
            self.p("word", "")
        self.p("word", "a")
        self.p("word", "cat")
        self.p("word", "aardvark")

        with self.assertRaises(ParseFailed):
            self.p("short_word", "")
        self.p("short_word", "a")
        self.p("short_word", "cat")
        with self.assertRaises(ParseFailed):
            self.p("short_word", "aardvark")

        self.p("maybe_word", "")
        self.p("maybe_word", "aardvark")


class TestParserValues(unittest.TestCase):
    def setUp(self):
        p = Parser()
        p.rule(Rule("num", [], Slice(Character([Range('0', '9')], False))))
        p.rule(Rule("three", [], Set(List([]), "l") & Append(Get("num")(), "l") & Append(Get("num")(), "l") & Append(Get("num")(), "l") & Get("l")))

        self.parser = p

    def test_three(self):
        self.assertEqual(["1", "2", "3"], self.parser.parse("three", [], "123"))
        with self.assertRaises(ParseFailed):
            self.parser.parse("three", [], "12b")
