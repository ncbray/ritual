import interpreter.testutil
import os.path
import parser
import compile
import unittest


class TestParser(interpreter.testutil.ParserTestCase):

    def setUp(self):
        self.parser = parser.p

    def test_full_func(self):
        self.p_ok('func_decl', 'fn foo(a:i32, b:i32) -> (i32, i32) {(b, a)}', args=[], value=parser.FuncDecl(
            parser.Token(3, 'foo'),
            [
                parser.Param(
                    parser.Token(7, 'a'),
                    parser.NamedTypeRef(parser.Token(9, 'i32')),
                ),
                parser.Param(
                    parser.Token(14, 'b'),
                    parser.NamedTypeRef(parser.Token(16, 'i32')),
                ),
            ],
            [
                parser.NamedTypeRef(parser.Token(25, 'i32')),
                parser.NamedTypeRef(parser.Token(30, 'i32')),
            ],
            parser.TupleLiteral(36, [
                parser.GetName(37, parser.Token(37, 'b')),
                parser.GetName(40, parser.Token(40, 'a')),
            ]),
        ))
