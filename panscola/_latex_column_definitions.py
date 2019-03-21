#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Parse column definitions in my custom syntax."""

# Standard Library
import collections
import copy
import itertools as it
import logging

# Third Party
import panflute as pf
import pyparsing as pp

# This Module
from panscola._parsers import (KeyValuePair, List, Token, column_definitions,
                               options)

logger = logging.getLogger(__name__)


_column_definition_classes = {}


class _MetaDefinition(type):
    def __new__(mcl, name, bases, attrs):
        identifier = attrs.get("identifier", None)

        if identifier:
            name = f"{identifier.upper()}Column"

        if identifier is not None and identifier in _column_definition_classes:
            return _column_definition_classes[identifier]

        optional_options = dict()
        internal_options = dict()

        for base in reversed(bases):
            oo = getattr(base, "optional_options", dict())
            optional_options.update(oo)

            _oo = getattr(base, "_optional_options", dict())
            optional_options.update(_oo)

            io = getattr(base, "internal_options", dict())
            internal_options.update(io)

        required_options = attrs.setdefault("required_options", list())
        optional_options.update(attrs.get("optional_options", dict()))
        attrs["optional_options"] = optional_options

        internal_options.update(attrs.get("internal_options", dict()))

        slots = set(attrs.get("__slots__", list()))
        slots.update(internal_options.keys())
        all_options = it.chain(required_options, optional_options.keys())

        for option in all_options:
            if option not in attrs:
                slots.add(option)

                continue

            attribute = attrs.get(option)

            slot = option

            if isinstance(attribute, property):
                slot = f"_{option}"

            slots.add(slot)

        attrs["__slots__"] = slots

        init_ = attrs.get("__init__")

        def init(self, *args, **kwargs):
            args = list(args)

            for key, value in self.internal_options.items():
                setattr(self, key, value)

            for option in required_options:
                if option in kwargs:
                    value = kwargs.pop(option)
                else:
                    try:
                        value = args.pop(0)
                    except IndexError:
                        raise ValueError(f"{option!r} needs to be specified")

                setattr(self, option, value)

            for option, default in optional_options.items():
                value = kwargs.pop(option, default)
                setattr(self, option, value)

            if init_ is not None:
                init_(self, *args, **kwargs)
            elif any((args, kwargs)):
                raise ValueError(
                    f"Got unexpected arguments: {args!r} or keyword arguments: {kwargs!r}"
                )

        attrs["__init__"] = init

        new = super().__new__(mcl, name, bases, attrs)
        _column_definition_classes[identifier] = new

        return new


class BaseColumnDefinition(metaclass=_MetaDefinition):
    option_name_transformer = False
    optional_options = {"multicolumn_definitions": None, "no_space_after":
                        None, "space_after": None}

    option_names = {}
    option_values = {bool: lambda b: str(b).lower()}

    internal_options = {"_no_left_padding": False, "_no_right_padding": False}

    def get_n_definition(self, n):
        if self.multicolumn_definitions is None:
            return copy.copy(self)

        if isinstance(self.multicolumn_definitions, BaseColumnDefinition):
            return self.multicolumn_definitions

        return self.multicolumn_definitions[n]

    def get_option_name(self, option):
        name = option

        if option in self.option_names:
            name = self.option_names[option]
        elif self.option_name_transformer:
            name = self.option_name_transformer(option)

        return name

    def get_option_value(self, option, option_value):
        if option in self.option_values:
            if callable(self.option_values[option]):
                return self.option_values[option](option_value)
            elif option_value in self.option_values[option]:
                return self.option_values[option][option_value]

        if type(option_value) in self.option_values:
            return self.option_values[type(option_value)](option_value)

        return option_value

    def indent(self, num):
        if not num:
            return [self]
        else:
            return [self] + [copy.deepcopy(self) for __ in range(num)]

    def __repr__(self):
        format_string = "{identifier}({options})"
        options_ = it.chain(self.required_options, self.optional_options.keys())
        options = ", ".join(f"{o}={repr(getattr(self, o))}" for o in options_)

        return format_string.format(identifier=self.identifier, options=options)

    def no_left_padding(self):
        self._no_left_padding = True

    def no_right_padding(self):
        self._no_right_padding = True

    def _latex(self, latex):
        before = "@{}" if self._no_left_padding else ""

        after = ""

        if self._no_right_padding or self.no_space_after:
            after = "@{}"

        if self.space_after:
            after = f"@{{\hskip {self.space_after}}}"

        return f"{before}{latex}{after}"

    @property
    def latex(self):
        raise NotImplementedError("You need to implement to_latex yourself.")


class _WithOptionString(metaclass=_MetaDefinition):
    _optional_options = {"baselineskip": "10pt", "raggedright": False}

    options_to_latex = {
        "raggedright": "\\RaggedRight\\arraybackslash",
        "baselineskip": "\\baselineskip={}",
    }

    @property
    def option_string(self):
        parts = [
            _WithOptionString.options_to_latex[o].format(getattr(self, o))
            for o in _WithOptionString._optional_options.keys()
            if getattr(self, o)
        ]

        if not parts:
            return ""

        return f">{{{''.join(parts)}}}"


def get_num_unit(string):
    for i, c in enumerate(string):
        if not c.isdigit():
            break
    number = float((string[:i]))
    unit = string[i:].strip()

    return number, unit


for identifier in "lrc":

    class SimpleColumn(BaseColumnDefinition):
        identifier = identifier

        @property
        def latex(self):
            return self._latex(self.identifier)


for identifier_ in "pmb":

    class ParagraphColumn(BaseColumnDefinition, _WithOptionString):
        identifier = identifier_
        required_options = ["width"]
        optional_options = {"indent_fraction": 0.1, "multicolumn_definitions": None}
        __slots__ = ["_widths_of_indents", "_identifier"]

        def get_n_definition(self, n):
            if self.multicolumn_definitions is None:
                multicolumn = copy.copy(self)
                multicolumn.width = sum(multicolumn._widths_of_indents[n:])
                multicolumn._identifier = "p"

                return multicolumn

            if isinstance(self.multicolumn_definitions, BaseColumnDefinition):
                return self.multicolumn_definitions

            return self.multicolumn_definitions[n]

        @property
        def width(self):
            width_ = self._width

            if isinstance(width_, float):
                width = f"{width_:.2f}\\textwidth"
            else:
                width = width_

            return width

        @width.setter
        def width(self, width):
            width_ = None
            try:
                width_ = float(width)
            except ValueError:
                width_ = str(width)

            self._width = width_

        def indent(self, num):
            if not num:
                return [self]
            else:
                # Each indent should indent by around 10 %
                width_ = self._width
                unit = ""

                widths_of_indents = []

                if isinstance(width_, str):
                    width_, unit = get_num_unit(width_)

                step = width_ * self.indent_fraction

                total_width = width_

                new_columns = []

                for __ in range(num):
                    new_width = step
                    total_width -= new_width
                    widths_of_indents.append(new_width)

                    if unit:
                        new_width = f"{new_width:.2d}{unit}"

                    new_column = copy.deepcopy(self)
                    new_column.width = new_width
                    new_column._widths_of_indents = widths_of_indents
                    new_column.no_space_after = True
                    new_columns.append(new_column)

                width_ = max(step, total_width)

                if unit:
                    width_ = f"{width_:.2d}{unit}"
                self.width = width_

                new_columns.append(self)
                widths_of_indents.append(width_)

                self._widths_of_indents = widths_of_indents

                return new_columns

        @property
        def latex(self):
            identifier = getattr(self, "_identifier", self.identifier)
            width = self.width
            option_string = self.option_string

            return self._latex(f"{option_string}{identifier}{{{self.width}}}")


class SColumn(BaseColumnDefinition):
    identifier = "S"
    required_options = []
    optional_options = {
        "table_format": "3.2",
        "add_integer_zero": None,
        "multicolumn_definitions": _column_definition_classes["l"](),
        "table_column_width": None,
        "table_number_alignment": None,
        "retain_explicit_plus": None,
        "detect_inline_weight": "math",
    }

    private_options = ["multicolumn_definitions", "no_space_after"]

    option_name_transformer = lambda self, o: "-".join(o.split("_"))

    @property
    def table_column_width(self):
        width = self._table_column_width

        if isinstance(width, float):
            return f"{width:.2f}\\textwidth"

        return width

    @table_column_width.setter
    def table_column_width(self, width):
        self._table_column_width = width

    @property
    def latex(self):
        options = {
            self.get_option_name(o): self.get_option_value(o, getattr(self, o))
            for o in self.optional_options.keys()
            if getattr(self, o) is not None and o not in self.private_options
        }
        options = ",".join(f"{k}={v}" for k, v in options.items())

        return self._latex(f"{self.identifier}[{options}]")


class XColumn(BaseColumnDefinition, _WithOptionString):
    identifier = "X"

    @property
    def latex(self):
        option_string = self.option_string

        return self._latex(f"{option_string}{self.identifier}")


def _process_value(value):
    if isinstance(value, List):
        return list(_column_specifiers_from_results(value.list))

    if isinstance(value, pp.ParseResults):
        return _column_specifier_from_one_result(value)

    return value


def _process_token(token, aliases, tokens):
    token = aliases.get(token, token)

    if token in tokens:
        key, value = tokens[token]

        return (aliases.get(key, key), value)

    return (aliases.get(token, token), True)


def _column_specifiers_from_results(results, ignore_errors=None):
    for result in results:
        yield _column_specifier_from_one_result(result)


def _column_specifier_from_one_result(result, ignore_errors=None):

    definition = result.asDict()

    identifier = definition["identifier"]
    required = definition.get("required", list())
    optional = definition.get("optional", list())

    optional = dict(
        (o.key, _process_value(o.value))
        if isinstance(o, KeyValuePair)
        else (o.token, True)
        for o in optional
    )

    try:
        column_specifier_class = _column_definition_classes[identifier]
    except KeyError:
        msg = "Could not find a column class with the identifier: %s"
        logger.debug(msg, identifier)

        if not ignore_errors:
            raise ValueError(msg % identifier)

        column_specifier_class = _column_definition_classes["l"]

    try:
        column_specifier = column_specifier_class(*required, **optional)
    except Exception as e:
        msg = "Encountered problems creating column specifier for identifier: %s; %s"
        logger.debug(msg, identifier, e)

        if not ignore_errors:
            raise ValueError(msg % (identifier, e))

        column_specifier = column_specifier_class = _column_definition_classes["l"]()

    return column_specifier


def column_specifiers_from_string(string, ignore_errors=None):
    results = column_definitions.parseString(string)

    for column_specifier in _column_specifiers_from_results(results, ignore_errors):
        yield column_specifier


def options_from_string(string, required_arguments=None, **optional_arguments):
    aliases = optional_arguments.pop("aliases", {})
    tokens = optional_arguments.pop("tokens", {})

    if any(len(k) < 2 for k in aliases.keys()):
        raise ValueError("Aliases must consist of at least two characters.")

    required_arguments = required_arguments or []

    result = options.parseString(string)
    required = result.get("required", list())

    required = [_process_value(v) for v in required]

    optional = result.get("optional", list())

    optional = dict(
        (aliases.get(o.key, o.key), _process_value(o.value))
        if isinstance(o, KeyValuePair)
        else _process_token(o.token, aliases, tokens)
        for o in optional
    )

    got_options = copy.copy(optional_arguments)

    for arg in required_arguments:
        if arg in optional:
            got_options[arg] = optional.pop(arg)

            continue

        try:
            got_options[arg] = required.pop(0)
        except IndexError:
            if not arg in optional_arguments:
                raise ValueError(f"{arg!r} is a required argument and wasn't given.")

    got_options.update(optional)

    if required:
        raise ValueError(f"Got unexpected positional arguments: {required!r}")

    return got_options


if __name__ == "__main__":
    print(
        options_from_string(
            "1,p[0.2],ul,mr",
            ["columns", "column_specifier"],
            aliases={"ul": "underline"},
            tokens={"mr": ("underline", "midrule")},
        )
    )
