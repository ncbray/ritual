import base


class LocationInfo(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'filename:string line:int column:int character:string text:string arrow:string'


def extractLocationInfo(filename, stream, pos):
    line = 1
    line_start = 0
    tabs = 0
    for i in range(0, pos):
        if stream[i] == '\n':
            line += 1
            line_start = i + 1
            tabs = 0
        elif stream[i] == '\t':
            tabs += 1
    line_end = pos
    while line_end < len(stream) and stream[line_end] != '\n':
        line_end += 1

    TAB_SIZE = 4
    text = stream[line_start:line_end].replace('\t', ' ' * TAB_SIZE)
    col = pos - line_start + tabs * (TAB_SIZE - 1)

    if pos < len(stream):
        c = repr(stream[pos])
    else:
        c = '<EOS>'

    return LocationInfo(filename, line, col, c, text, ' '*col + '^')


class CompileStatus(object):
    def __init__(self):
        self.sources = []
        self.loc = 0
        self.errors = 0

    def add_source(self, filename, text):
        loc = self.loc
        self.loc += len(text) + 1 # For EOF
        self.sources.append((loc, self.loc, filename, text))
        return loc

    def extract_location_info(self, loc):
        for begin, end, filename, text in self.sources:
            if begin <= loc and loc < end:
                return extractLocationInfo(filename, text, loc - begin)
        assert False, loc

    def error(self, msg, loc=None):
        if loc is None:
            print 'error: %s' % msg
        else:
            info = self.extract_location_info(loc)
            print '%s:%d:%d: error: %s\n%s\n%s' % (info.filename, info.line, info.column, msg, info.text, info.arrow)
        self.errors += 1

    def halt_if_errors(self):
        if self.errors:
            raise Exception('Halting due to errors.')
