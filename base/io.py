class Block(object):
    def __init__(self, out):
        assert isinstance(out, TabbedWriter), out
        self.out = out

    def __enter__(self):
        self.out.indent()

    def __exit__(self, type, value, traceback):
        self.out.dedent()


class TabbedWriter(object):
    def __init__(self, out):
        self.out = out
        self.indent_level = 0
        self.indent_text = ''
        self.buffer = ''

    def indent(self):
        #assert not self.dirty
        self.indent_level += 1
        self.indent_text = self.indent_level * '    '

    def dedent(self):
        # Can't check dirty because this may be an exception.
        self.indent_level -= 1
        self.indent_text = self.indent_level * '    '

    def block(self):
        return Block(self)

    # TODO behaves badly when accumulating whitespace.
    def write(self, text):
        for l in text.splitlines(True):
            self.buffer += l
            eol = l.endswith('\n')
            if not eol:
                return
            b = self.buffer.rstrip()
            self.buffer = ''
            if b:
                self.out.write(self.indent_text)
                self.out.write(b)
            self.out.write('\n')
