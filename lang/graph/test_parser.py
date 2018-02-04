import unittest

import interpreter.testutil
import parser
import semantic


class TestParser(interpreter.testutil.ParserTestCase):

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
        result = self.p_ok('file', src)
        py_src = semantic.process_file(src, result)
        #print py_src
        out = {}
        semantic.compile_source('test', py_src, out)