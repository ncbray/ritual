#!/usr/bin/python

import collections
import optparse
import sys

import interpreter.location
import lang.scale.compile
import lang.scale.generate_cpp


CompileConfig = collections.namedtuple('CompileConfig', 'root module out')


def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("--root", dest="root", metavar="DIR")
    parser.add_option("--module", dest="module", metavar="MODULE")
    parser.add_option("--out", dest="out", metavar="FILE")

    (options, args) = parser.parse_args()
    if not options.root:
        parser.error('Please specify source root.')
    if not options.module:
        parser.error('Please specify module.')
    if not options.out:
        parser.error('Please specify output.')

    if len(args) != 0:
        parser.error('No arguments.')
    return CompileConfig(options.root, options.module, options.out)


def main():
    config = parse_args()

    status = interpreter.location.CompileStatus()
    p = lang.scale.compile.frontend(config.root, config.module.split('.'), status)
    status.halt_if_errors()
    with open(config.out, 'w') as f:
        lang.scale.generate_cpp.generate_source(p, f)

if __name__ == '__main__':
    try:
        main()
    except interpreter.location.HaltCompilation:
        sys.exit(1)
    sys.exit(0)

