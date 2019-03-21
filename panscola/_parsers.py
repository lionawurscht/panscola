#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Standard Library
import collections

# Third Party
import pyparsing as pp

KeyValuePair = collections.namedtuple("KeyValuePair", ["key", "value"])
Token = collections.namedtuple("Token", ["token"])
List = collections.namedtuple("List", ["list"])


# Definition should look like this I[required_option1,required_option2,..<token or key-value pair>]
# Common types that are gonna be reused


#  ----------------------
#  Will be filled later
#  ----------------------

column_definition_ = pp.Forward()
column_definitions_ = pp.Forward()

#  ----------------------
#  Commonly used parts
#  ----------------------


boolean = pp.Literal("true").setParseAction(lambda *__: True) | pp.Literal(
    "false"
).setParseAction(lambda *__: False)

number = pp.pyparsing_common.number
string = pp.QuotedString("'", escChar="\\") | pp.QuotedString('"', escChar="\\")


value = (
    column_definition_
    | boolean
    | number
    | string
    | (
        pp.Suppress(pp.Literal("["))
        + column_definitions_
        + pp.Suppress(pp.Literal("]"))
    ).setParseAction(lambda tokens: List(list(t for t in tokens)))
)
required = value
requireds = pp.delimitedList(required).setResultsName("required")

token_ = ~boolean + pp.Combine(
    pp.Word(pp.alphas + "_") + pp.Optional(pp.Word(pp.alphanums + "_"))
)

key = token_.copy()
is_ = pp.Suppress(pp.Literal("="))

key_value_pair = pp.Group(key + is_ + value).setParseAction(
    lambda tokens: KeyValuePair(*tokens[0])
)

token = token_.copy().setParseAction(lambda tokens: Token(tokens[0]))

optional = key_value_pair | token
optionals = pp.delimitedList(optional).setResultsName("optional")

options = (requireds + pp.Suppress(",") + optionals) | requireds | optionals

identifier = pp.Word(pp.alphas, max=1).setResultsName("identifier") + ~pp.FollowedBy(
    pp.Literal("=") | pp.Word(pp.alphas)
)

column_definition = pp.Group(
    identifier
    + pp.Optional(pp.Suppress(pp.Literal("[")) + options + pp.Suppress(pp.Literal("]")))
)
column_definition_ << column_definition
column_definitions = pp.delimitedList(column_definition)
column_definitions_ << column_definitions


if __name__ == "__main__":
    pass
