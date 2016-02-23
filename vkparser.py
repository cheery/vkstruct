from chartparser import Nonterminal, Terminal, Rule, preprocess
import re

def parse_member(tag):
    return parse(member_parser, c_tokenize(tag), tag)

def parse_funcpointer(tag):
    return parse(funcpointer_parser, c_tokenize(tag), tag)

def parse(pg, tokens, root): 
    parser = pg()
    for is_tag, token in tokens:
        if is_tag:
            name = tagtypes[token.name]
        else:
            name = token
            if name not in parser.expect:
                name = tag_text
        if name not in parser.expect:
            message = "\n".join([
                "input: {}".format("".join(map(str, root.contents))),
                "at:    {}".format(token),
                "expected: {}".format(", ".join(map(str, parser.expect)))
            ])
            print "{}".format(root)
            raise Exception("Parse error: \n" + message)
        assert name in parser.expect, (root, name, token, parser.expect)
        parser.step(name, token)
    return parser.traverse(post, blank)

funcpointer = Nonterminal("funcpointer")
#typedef = Nonterminal("typedef")
arglist = Nonterminal("arglist")
member = Nonterminal("member")

specifier = Nonterminal("specifier")
declarator = Nonterminal("declarator")
qualifier = Nonterminal("qualifier")
tag_name = Nonterminal("<name/>")
tag_type = Nonterminal("<type/>")
tag_enum = Nonterminal("<enum/>")
tag_text = Nonterminal("<text/>")

constant = Nonterminal("constant")

tagtypes = {
    "name": tag_name,
    "type": tag_type,
    "enum": tag_enum}

grammar = [
    Rule(funcpointer, [
        "typedef", specifier,
        "(", "VKAPI_PTR", "*", tag_name, ")",
        "(", arglist, ")", ";"], "funcpointer"),
    Rule(arglist, []),
    Rule(arglist, ["void"], "blank"),
    Rule(arglist, [member], "first_arg"),
    Rule(arglist, [arglist, ",", member], "another_arg"),

    Rule(member, [specifier, declarator], "member"),
    Rule(member, [member, "[", constant, "]"], "array_member"),
    Rule(declarator, [tag_name], "tag_declarator"),
    Rule(declarator, [tag_text], "text_declarator"),
    Rule(specifier, [specifier, "*"], "pointer_specifier"),
    Rule(specifier, [specifier, "const", "*"], "pointer_specifier"),
    Rule(specifier, ["struct",  tag_type], "struct_specifier"),
    Rule(specifier, [qualifier, tag_type], "tag_specifier"),
    Rule(specifier, [qualifier, tag_text], "text_specifier"),
    Rule(qualifier, []),
    Rule(qualifier, ["const"], "ignored_qualifier"),
    Rule(constant, [tag_text], "tag_text_constant"),
    Rule(constant, [tag_enum], "tag_enum_constant"),
]

member_parser = preprocess(grammar, member)
funcpointer_parser = preprocess(grammar, funcpointer)

def post(rule, args):
    a = rule.annotation
    if a == "funcpointer":
        restype = args[1]
        name = args[5].text
        args = args[8]
        return Node("funcpointer", restype, name, args)
    if a == "blank":
        return []
    if a == "first_arg":
        return [args[0]]
    if a == "another_arg":
        return args[0] + [args[2]]
    if a == "member":
        return Node("member", *args)
    if a == "array_member":
        member = args[0]
        constant = args[2]
        return Node(member.name, 
            Node("array", member.args[0], constant),
            member.args[1]
        )
    if a == "tag_specifier":
        return Node("type", args[1].text)
    if a == "text_specifier":
        return Node("type", args[1])
    if a == "pointer_specifier":
        return Node("pointer", args[0])
    if a == "struct_specifier":
        return Node("struct", args[1].text)
    if a == "tag_declarator":
        return args[0].text
    if a == "text_declarator":
        return args[0]
    if a == "tag_enum_constant":
        return Node("enum", args[0].text)
    if a == "tag_text_constant":
        return Node("constant", int(args[0]))
    if a == "ignored_qualifier":
        return None
    assert False, (a, args)

def blank(symbol):
    if symbol == qualifier:
        return None
    if symbol == arglist:
        return []
    assert False, symbol

class Node(object):
    def __init__(self, name, *args):
        self.name = name
        self.args = args

    def __repr__(self):
        return "({} {})".format(
            self.name, " ".join(map(repr, self.args)))

    def __getitem__(self, index):
        return self.args[index]

    def __len__(self):
        return len(self)

def c_tokenize(field):
    for tag in field:
        if tag.name != None:
            yield True, tag
        else:
            text = tag.strip()
            while text != "":
                digits = re.match(r"^(\d+)(.*)$", text, re.DOTALL)
                symbols = re.match(r"^(\[|\]|\*|\(|\)|;|,)(.*)$", text, re.DOTALL)
                const_t = re.match(r"^(\w+)(.*)$", text, re.DOTALL)
                if digits:
                    d, text = digits.groups()
                    yield False, d
                elif symbols:
                    s, text = symbols.groups()
                    yield False, s
                elif const_t:
                    c, text = const_t.groups()
                    yield False, c
                else:
                    assert False, (text, digits, const_t, symbols)
                text = text.strip()
