#!/usr/bin/python

import collections
import cStringIO
import os.path
import optparse
import sys

import ritual.interpreter.location
import ritual.lang.scale.compile
import ritual.lang.scale.generate_cpp


CompileConfig = collections.namedtuple('CompileConfig', 'system root module out')


def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("--system", dest="system", metavar="DIR")
    parser.add_option("--root", dest="root", metavar="DIR")
    parser.add_option("--module", dest="module", metavar="MODULE")
    parser.add_option("--out", dest="out", metavar="FILE")

    (options, args) = parser.parse_args()
    if not options.system:
        parser.error('Please specify system dir.')
    if not os.path.isdir(options.system):
        parser.error('--system should refer to a directory.')
    if not options.root:
        parser.error('Please specify source root.')
    if not os.path.isdir(options.root):
        parser.error('--root should refer to a directory.')
    if not options.module:
        parser.error('Please specify module.')
    if not options.out:
        parser.error('Please specify output.')

    if len(args) != 0:
        parser.error('No arguments.')
    return CompileConfig(options.system, options.root, options.module, options.out)


def file_is_same(path, text):
    if not os.path.isfile(path):
        return False
    with open(path) as f:
        return f.read() == text


def main():
    config = parse_args()

    status = ritual.interpreter.location.CompileStatus()
    p = ritual.lang.scale.compile.frontend(config.system, config.root, config.module.split('.'), status)
    status.halt_if_errors()
    buf = cStringIO.StringIO()
    ritual.lang.scale.generate_cpp.generate_source(p, buf)
    src = buf.getvalue()

    if not file_is_same(config.out, src):
        with open(config.out, 'w') as f:
            f.write(src)

if __name__ == '__main__':
    try:
        main()
    except ritual.interpreter.location.HaltCompilation:
        sys.exit(1)
    sys.exit(0)

