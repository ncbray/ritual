import unittest

import parser

class TestParser(unittest.TestCase):
    def test_self_hosting(self):
        parser.p.parse('file', parser.src)
