class Block(object):
    def __init__(self, out, if_empty=None):
        assert isinstance(out, TabbedWriter), out
        self.out = out
        self.if_empty = if_empty

    def __enter__(self):
        self.out.indent()
        self.pos = self.out.pos

    def __exit__(self, type, value, traceback):
        if self.pos == self.out.pos and self.if_empty:
            self.out.write(self.if_empty)
        self.out.dedent()


class TabbedWriter(object):
    def __init__(self, out):
        self.out = out
        self.indent_level = 0
        self.indent_text = ''
        self.buffer = ''
        self.pos = 0

    def indent(self):
        #assert not self.dirty
        self.indent_level += 1
        self.indent_text = self.indent_level * '    '

    def dedent(self):
        # Can't check dirty because this may be an exception.
        self.indent_level -= 1
        self.indent_text = self.indent_level * '    '

    def block(self, if_empty=None):
        return Block(self, if_empty)

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
                self.pos += 1
            self.out.write('\n')
