def setup():
    import ritual.lang.base
    import os.path

    src_file = os.path.join(os.path.dirname(__file__), 'scale.ritual')
    ritual.lang.base.generate_parser(src_file, True, globals())

    def int_to_rune(i):
        return chr(i)

    def runes_to_string(runes):
        return ''.join(runes)

    def string_to_int(text, base):
        return int(text, base)

    return buildParser(
        int_to_rune=int_to_rune,
        runes_to_string=runes_to_string,
        string_to_int=string_to_int
    )


p = setup()
