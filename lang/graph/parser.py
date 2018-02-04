def setup():
    import os.path
    import phase1.parser

    src_file = os.path.join(os.path.dirname(__file__), 'graphlang.ritual')
    with open(src_file) as f:
        src = f.read()
    phase1.parser.compile(src_file, src, globals())
    return buildParser()


p = setup()
