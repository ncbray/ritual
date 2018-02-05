def setup():
    import lang.base
    import os.path

    src_file = os.path.join(os.path.dirname(__file__), 'graphlang.ritual')
    lang.base.generate_parser(src_file, True, globals())
    return buildParser()


p = setup()
