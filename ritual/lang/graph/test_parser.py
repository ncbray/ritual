import unittest

from ritual.interpreter.testutil import ParserTestCase

from . import parser
from . import semantic


class TestParser(ParserTestCase):

    def setUp(self):
        self.parser = parser.p

    def test_compile(self):
        src = r"""
struct Op {
}
struct Value {
}
edge Control {
    scalar Op {n, f};
    bag Op prev;
}
edge Use {
    bag Value uses;
    indexed Op inputs;
}
edge Def {
    indexed Op outputs;
    scalar Value definition;
}
"""
        name = 'test'
        result = self.p_ok('file', src)
        py_src = semantic.process_file(name, src, result)
        out = {}
        semantic.compile_source(name, py_src, out)
