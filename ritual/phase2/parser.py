externs = {
    'chr': unichr,
    'chars_to_string': lambda chars: ''.join(chars),
    'hex_to_int': lambda text: int(text, 16),
    'dec_to_int': lambda text: int(text, 10),
}

def setup():
    import os.path
    import ritual.phase1.parser

    src_file = os.path.join(os.path.dirname(__file__), 'phase2.ritual')
    with open(src_file) as f:
        src = f.read()
    ritual.phase1.parser.compile(src_file, src, globals())
    p = buildParser(**externs)
    return p, src


p, src = setup()
