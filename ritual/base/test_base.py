from ritual import base
import unittest

class Foo(object, metaclass=base.TreeMeta):
    __schema__ = 'num:int@[no_compare] a:string b:string'


class Bar(object, metaclass=base.TreeMeta):
    __schema__ = 'num:int foo:Foo'


class TestSimpleParser(unittest.TestCase):
    def test_foo_equal(self):
        a = Foo(1, 'a', 'b')
        b = Foo(1, 'a', 'b')
        c = Foo(2, 'a', 'b')
        d = Foo(1, 'b', 'b')
        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(d, d)
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertNotEqual(a, d)

    def test_bar_equal(self):
        self.assertEqual(Bar(0, Foo(1, 'a', 'b')), Bar(0, Foo(2, 'a', 'b')))
        self.assertNotEqual(Bar(0, Foo(1, 'a', 'b')), Bar(1, Foo(1, 'a', 'b')))
        self.assertNotEqual(Bar(0, Foo(1, 'a', 'b')), Bar(0, Foo(1, 'b', 'b')))
