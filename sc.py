#!/usr/bin/env python3

import argparse
import io
import os.path
import sys

import ritual.interpreter.location
import ritual.lang.scale.compile
import ritual.lang.scale.generate_cpp


def parse_args():
    parser = argparse.ArgumentParser(description='Compile a Scale program.')
    parser.add_argument('--system', dest='system', required=True, metavar='DIR', help='Directory holding system sources.')
    parser.add_argument('--root', dest='root', required=True, metavar='DIR', help='Directory holding program sources.')
    parser.add_argument('--module', dest='module', required=True, metavar='MODULE', help='Name of the module to compile.')
    parser.add_argument('--deps', dest='deps', metavar='FILE', help='File to output build dependency information.')
    parser.add_argument('--verbose', action='store_true', help='Print information useful for debugging the compiler.')
    parser.add_argument('--out', dest='out', required=True, metavar='FILE', help='File to output generated C++ source.')

    options = parser.parse_args()
    if not os.path.isdir(options.system):
        parser.error('--system should refer to a directory.')
    if not os.path.isdir(options.root):
        parser.error('--root should refer to a directory.')

    return options


def file_is_same(path, text):
    if not os.path.isfile(path):
        return False
    with open(path) as f:
        return f.read() == text


# Get a list of all Python files that have been loaded.
# This allows a build system to know when the compiler has changed.
# Note: this isn't complete - it can miss dynamically generated code from non-python files.
# But close enough.
def get_loaded_python_files(files):
    for name, m in sys.modules.items():
        if not m or not hasattr(m, '__file__'):
            continue
        fn = m.__file__
        if fn.endswith('.pyc') or fn.endswith('.pyo'):
            src = fn[:-1]
            if os.path.exists(src):
                fn = src
        files.add(fn)


def main():
    config = parse_args()
    status = ritual.interpreter.location.CompileStatus(debug=config.verbose)

    # Compile
    p, files = ritual.lang.scale.compile.frontend(config.system, config.root, config.module.split('.'), status)
    status.halt_if_errors()
    buf = io.StringIO()
    ritual.lang.scale.generate_cpp.generate_source(p, buf)
    src = buf.getvalue()

    # Write the generated source to disk if it has changed.
    if not file_is_same(config.out, src):
        with open(config.out, 'w') as f:
            f.write(src)

    # List all files used during compilation, to assist the build system.
    if config.deps:
        get_loaded_python_files(files)
        files = sorted(files)
        with open(config.deps, 'w') as f:
            f.write(config.out)
            f.write(': \\\n')
            for fn in files:
                f.write(fn)
                f.write(' \\\n')
            f.write('\n')


if __name__ == '__main__':
    try:
        main()
    except ritual.interpreter.location.HaltCompilation:
        sys.exit(1)
    sys.exit(0)

