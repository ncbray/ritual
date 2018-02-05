import os.path
import phase1.parser

base_file = os.path.join(os.path.dirname(__file__), 'base.ritual')


def generate_parser(src_file, inject_base, glbls):
    src = ''
    with open(src_file) as f:
        src += f.read()
    if inject_base:
        # Inject at the end to avoid shifting line numbers.
        # TODO some sort of real module system.
        src += '\n\n'
        with open(base_file) as f:
            src += f.read()
    phase1.parser.compile(src_file, src, glbls)