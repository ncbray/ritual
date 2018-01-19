import unittest

class ParserTestCase(unittest.TestCase):
    def p_ok(self, name, text, value=None, args=()):
        result =  self.parser.parse(name, args, text, True)
        if not result.ok:
            self.fail(result.error_message())
        if value is not None:
            self.assertEqual(value, result.value)
        return result.value

    def p_fail(self, name, text, args=()):
        result = self.parser.parse(name, args, text, True)
        self.assertEqual(result.ok, False)
