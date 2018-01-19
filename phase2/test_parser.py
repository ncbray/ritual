import unittest

import parser


class TestParser(unittest.TestCase):
    def test_self_hosting(self):
        parser.p.parse('file', [], parser.src)

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
            self.assertEqual(parser.p.parse("escape_char", [], text), result)

    def test_args(self):
        parser.p.parse("file", [], r"""
func bracket(s:string):string {
    <$"["; $s; $"]">
}
""")
