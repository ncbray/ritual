from interpreter import *
import interpreter.testutil

class TestSimpleParser(interpreter.testutil.ParserTestCase):
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

    def test_t_match(self):
        self.p_ok("t", "true")
        self.p_fail("t", "true ")
        self.p_fail("t", "false")
        self.p_fail("t", "")
        self.p_fail("t", "tru")

    def test_b(self):
        self.p_ok("b", "true")
        self.p_ok("b", "false")
        self.p_fail("b", "maybe")

    def test_num(self):
        self.p_ok("num", "0")
        self.p_ok("num", "5")
        self.p_ok("num", "9")
        self.p_fail("num", "")
        self.p_fail("num", "d")
        self.p_fail("num", "!")

    def test_not_num(self):
        self.p_ok("not_num", "d")
        self.p_ok("not_num", "!")
        self.p_fail("not_num", "")
        self.p_fail("not_num", "0")
        self.p_fail("not_num", "5")
        self.p_fail("not_num", "9")

    def test_letter(self):
        self.p_ok("letter", "a")
        self.p_ok("letter", "g")
        self.p_ok("letter", "z")
        self.p_ok("letter", "A")
        self.p_ok("letter", "G")
        self.p_ok("letter", "Z")
        self.p_fail("letter", "")
        self.p_fail("letter", "7")
        self.p_fail("letter", "!")

    def test_word(self):
        self.p_fail("word", "")
        self.p_ok("word", "a")
        self.p_ok("word", "cat")
        self.p_ok("word", "aardvark")

        self.p_fail("short_word", "")
        self.p_ok("short_word", "a")
        self.p_ok("short_word", "cat")
        self.p_fail("short_word", "aardvark")

        self.p_ok("maybe_word", "")
        self.p_ok("maybe_word", "aardvark")


class TestParserValues(interpreter.testutil.ParserTestCase):
    def setUp(self):
        p = Parser()
        p.rule(Rule("num", [], Slice(Character([Range('0', '9')], False))))
        p.rule(Rule("three", [], Set(List([]), "l") & Append(Get("num")(), "l") & Append(Get("num")(), "l") & Append(Get("num")(), "l") & Get("l")))
        self.parser = p

    def test_three(self):
        self.p_ok("three", "123", ["1", "2", "3"])
        self.p_fail("three", "12b")
