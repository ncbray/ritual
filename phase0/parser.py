class Matcher(object):
    def match(self, parser):
        raise NotImplementedError()

    def __and__(self, other):
        return Sequence([self, other])

    def __or__(self, other):
        return Choice([self, other])

    def __call__(self, *args):
        return Call(self, args)


class Sequence(Matcher):
    def __init__(self, children):
        for child in children:
            assert isinstance(child, Matcher), child
        self.children = children

    def match(self, parser):
        result = None
        for m in self.children:
            result = m.match(parser)
            if not parser.ok:
                return result
        return result

    def __and__(self, other):
        if isinstance(other, Sequence):
            others = other.children
        else:
            others = [other]
        return Sequence(self.children + others)

    def source(self):
        return '&'.join([o.source() for o in self.children])

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.children)


class Choice(Matcher):
    def __init__(self, children):
        for child in children:
            assert isinstance(child, Matcher), child
        self.children = children

    def match(self, parser):
        result = None
        pos = parser.pos
        for m in self.children:
            result = m.match(parser)
            if parser.ok:
                return result
            parser.recover(pos)
        parser.fail()
        return result

    def __or__(self, other):
        if isinstance(other, Choice):
            others = other.children
        else:
            others = [other]
        return Choice(self.children + others)

    def source(self):
        return '|'.join([o.source() for o in self.children])

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.children)


class Repeat(Matcher):
    def __init__(self, expr, min, max):
        assert isinstance(expr, Matcher), expr
        self.expr = expr
        self.min = min
        self.max = max

    def match(self, parser):
        count = 0
        while count < self.min:
            self.expr.match(parser)
            if not parser.ok:
                return
            count += 1

        while count < self.max or self.max <= 0:
            pos = parser.pos
            self.expr.match(parser)
            if not parser.ok:
                parser.recover(pos)
                return
            count += 1
        # TODO collect list?

    def __repr__(self):
        return '%s(%r, %r, %r)' % (type(self).__name__, self.expr, self.min, self.max)


class Call(Matcher):
    def __init__(self, expr, args):
        assert isinstance(expr, Matcher), expr
        for arg in args:
            assert isinstance(arg, Matcher), arg
        self.expr = expr
        self.args = tuple(args)

    def match(self, parser):
        expr = self.expr.match(parser)
        if not parser.ok:
            return expr
        values = []
        for arg in self.args:
            value = arg.match(parser)
            if not parser.ok:
                return value
            values.append(value)
        if not isinstance(expr, Callable):
            parser.internalError(self, "Cannot call %r" % expr)
        return expr.call(parser, values)

    def source(self):
        return self.name + '()'

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.expr, self.args)


class Any(Matcher):
    def match(self, parser):
        if parser.hasNext():
            parser.consume()
        else:
            parser.fail()

    def source(self):
        return '.'


class Range(object):
    __slots__ = ['lower', 'upper']

    def __init__(self, lower, upper):
        assert len(lower) == 1
        assert len(upper) == 1
        assert lower <= upper
        self.lower = lower
        self.upper = upper

    def source(self):
        # TODO escape
        if self.lower == self.upper:
            return self.lower
        else:
            return '%s-%s' % (self.lower, self.upper)

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.lower, self.upper)


class Character(Matcher):
    def __init__(self, ranges, invert):
        for r in ranges:
            assert isinstance(r, Range), r
        assert isinstance(invert, bool), invert
        self.ranges = tuple(ranges)
        self.invert = invert

    def match(self, parser):
        if not parser.hasNext():
            parser.fail()
            return
        c = parser.peek()

        matches = False
        for r in self.ranges:
            if r.lower <= c <= r.upper:
                matches = True
                break

        if matches != self.invert:
            parser.consume()
        else:
            parser.fail()
        return c

    def source(self):
        return ('[^%s]' if self.invert else '[%s]') % ''.join([r.source() for r in self.ranges])

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.ranges, self.invert)


class MatchValue(Matcher):
    def __init__(self, expr):
        self.expr = expr

    def match(self, parser):
        expr = self.expr.match(parser)
        if not parser.ok:
            return expr

        for c in expr:
            if not parser.hasNext() or parser.peek() != c:
                parser.fail()
                return
            parser.consume()
        return expr

    def source(self):
        return repr(self.text)

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.expr)


class Slice(Matcher):
    def __init__(self, expr):
        self.expr = expr

    def match(self, parser):
        pos = parser.pos
        result = self.expr.match(parser)
        if parser.ok:
            result = unicode(parser.stream[pos:parser.pos])
        return result

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.expr)


class Get(Matcher):
    def __init__(self, name):
        self.name = name

    def match(self, parser):
        n = self.name
        lcls = parser.stack[-1].scope
        if n in lcls:
            return lcls[n]
        elif n in parser.rules:
            return parser.rules[n]
        else:
            parser.internalError(self, "Unbound name %r" % n)

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.name)


class Set(Matcher):
    def __init__(self, expr, name):
        self.expr = expr
        self.name = name

    def match(self, parser):
        result = self.expr.match(parser)
        if parser.ok:
            lcls = parser.stack[-1].scope
            lcls[self.name] = result
        return result

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.expr, self.name)


class Append(Matcher):
    def __init__(self, expr, name):
        self.expr = expr
        self.name = name

    def match(self, parser):
        result = self.expr.match(parser)
        if parser.ok:
            lcls = parser.stack[-1].scope
            lcls[self.name].append(result)
        return result

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.expr, self.name)


class List(Matcher):
    def __init__(self, args):
        self.args = tuple(args)

    def match(self, parser):
        values = []
        for arg in self.args:
            value = arg.match(parser)
            if not parser.ok:
                return value
            values.append(value)
        return values


class Literal(Matcher):
    def __init__(self, value):
        self.value = value

    def match(self, parser):
        return self.value

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.value)


class Callable(object):
    pass


class Rule(Callable):
    def __init__(self, name, body):
        self.name = name
        self.body = body

    def call(self, parser, args):
        assert not args, args
        parser.enterFrame(self.name)
        result = self.body.match(parser)
        parser.exitFrame()
        return result


class Native(Callable):
    def __init__(self, name, func):
        self.name = name
        self.func = func

    def call(self, parser, args):
        try:
            return self.func(*args)
        except:
            parser.printStack()
            raise

class ParseFailed(Exception):
    pass

class StackFrame(object):
    def __init__(self, name):
        self.name = name
        self.scope = {}

class Parser(object):
    def __init__(self):
        self.rules = {}

    def rule(self, rule):
        assert rule.name not in self.rules
        self.rules[rule.name] = rule

    def hasNext(self):
        return self.pos < len(self.stream)

    def peek(self):
        return self.stream[self.pos]

    def consume(self):
        self.pos += 1

    def fail(self):
        self.deepest = max(self.deepest, self.pos)
        self.ok = False
        #print
        #self.printStack()

    def recover(self, pos):
        self.pos = pos
        self.ok = True

    def enterFrame(self, name):
        self.stack.append(StackFrame(name))

    def exitFrame(self):
        self.stack.pop()

    def printStack(self):
        for frame in reversed(self.stack):
            print '    %-25s %r' % (frame.name, frame.scope)

    def internalError(self, node, msg):
        print msg
        print node
        self.printStack()
        raise Exception(msg)

    def parse(self, name, text):
        self.stream = text
        self.pos = 0
        self.deepest = 0
        self.ok = True
        self.stack = []
        result = self.rules[name].call(self, [])
        if self.hasNext():
            self.fail()
        if not self.ok:
            a = max(self.deepest - 1, 0)
            b = min(self.deepest + 2, len(self.stream))
            clip = self.stream[a:b]
            raise ParseFailed("Error at %d: %r" % (self.deepest, clip))
        return result
