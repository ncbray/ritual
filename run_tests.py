#!/usr/bin/env python3

import os.path
import unittest

if __name__ == '__main__':
    loader = unittest.TestLoader()
    #loader.testMethodPrefix = 'test_parser'
    suite = loader.discover(os.path.dirname(__file__))
    unittest.TextTestRunner(verbosity=2).run(suite)
