#!/usr/bin/env python3

import phase1.parser
import sys

file_name = sys.argv[1]

with open(file_name) as f:
    data = f.read()

print(phase1.parser.compile_src(file_name, data))