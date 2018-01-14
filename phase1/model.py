import base
import phase0.parser


class RuleDecl(object):
    __metaclass__ = base.TreeMeta
    __schema__ = 'name:string rt:string body:phase0.parser.Matcher'


def registerTypes(p):
    p.rule(phase0.parser.Native('RuleDecl', RuleDecl))
