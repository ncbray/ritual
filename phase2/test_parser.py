import unittest

import interpreter.testutil
import parser


class TestParser(interpreter.testutil.ParserTestCase):

    def setUp(self):
        self.parser = parser.p

    def test_self_hosting(self):
        self.p_ok('file', parser.src)

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

    def test_args(self):
        self.p_ok("file", r"""
func bracket(s:string):string {
    <$"["; $s; $"]">
}
""")
