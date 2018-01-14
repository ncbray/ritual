import base

class Matcher(object):
    def match(self, parser):
        raise NotImplementedError()

    def __and__(self, other):
        return Sequence([self, other])

    def __or__(self, other):
        return Choice([self, other])

    def __call__(self, *args):
        return Call(self, list(args))


class Sequence(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'children:[]Matcher'

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


class Choice(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'children:[]Matcher'

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


class Repeat(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher min:int max:int'

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


class Call(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher args:[]Matcher'

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


class Any(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = ''

    def match(self, parser):
        if parser.hasNext():
            parser.consume()
        else:
            parser.fail()


class Range(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'lower:rune upper:rune'


class Character(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'ranges:[]Range invert:bool'

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


class MatchValue(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher'

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


class Slice(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher'

    def match(self, parser):
        pos = parser.pos
        result = self.expr.match(parser)
        if parser.ok:
            result = unicode(parser.stream[pos:parser.pos])
        return result


class Get(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string'

    def match(self, parser):
        n = self.name
        lcls = parser.stack[-1].scope
        if n in lcls:
            return lcls[n]
        elif n in parser.rules:
            return parser.rules[n]
        else:
            parser.internalError(self, "Unbound name %r" % n)


class Set(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher name:string'

    def match(self, parser):
        result = self.expr.match(parser)
        if parser.ok:
            if isinstance(result, Callable):
                parser.internalError(self, "Should not be storing a Callable to %r" % self.name)
            lcls = parser.stack[-1].scope
            lcls[self.name] = result
        return result


class Append(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'expr:Matcher name:string'

    def match(self, parser):
        result = self.expr.match(parser)
        if parser.ok:
            n = self.name
            if isinstance(result, Callable):
                parser.internalError(self, "Should not be storing a Callable to %r" % n)
            lcls = parser.stack[-1].scope
            if n not in lcls:
                parser.internalError(self, "Unbound name %r" % n)
            tgt = lcls[n]
            if not isinstance(tgt, list):
                parser.internalError(self, "Append target %r is a %r and not a list" % (n, type(tgt)))
            tgt.append(result)
        return result


class List(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'args:[]Matcher'

    def match(self, parser):
        values = []
        for arg in self.args:
            value = arg.match(parser)
            if not parser.ok:
                return value
            values.append(value)
        return values


class Literal(Matcher):
    __metaclass__ = base.TreeMeta
    __schema__ = 'value:*'

    def match(self, parser):
        return self.value


class Callable(object):
    __slots__ = []


class Rule(Callable):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string body:Matcher'

    def call(self, parser, args):
        assert not args, args
        parser.enterFrame(self.name)
        result = self.body.match(parser)
        parser.exitFrame()
        return result


class Native(Callable):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string func:*'

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
