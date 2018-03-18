#!/usr/bin/env python
"""Utility functions that are reused throughout the project."""
import copy
import io
import string
import logging

import bs4
import panflute as pf

logging.basicConfig(level=logging.WARN)


class Dependent:

    def __init__(self, object_, dependencies=None):
        if dependencies is not None:
            self.dependencies = dependencies
        else:
            self.dependencies = []

        self.object_ = object_

    def __repr__(self):
        return repr(self.object_)

    def add_dependency(self, dependency):
        self.dependencies.append(dependency)

    def add_dependencies(self, *dependencies):
        for dependency in dependencies:
            self.add_dependency(dependency)


def resolve_dependencies(dependent, resolved=None, seen=None):
    if resolved is None:
        resolved = []

    if seen is None:
        seen = []

    if isinstance(dependent, list):
        for d in dependent:
            resolve_dependencies(d, resolved, seen)

    else:
        if dependent not in resolved:
            seen.append(dependent)

            for dependency in dependent.dependencies:
                if dependency not in resolved:
                    if dependency in seen:
                        raise Exception('Circular dependency')
                    resolve_dependencies(dependency, resolved, seen)
            resolved.append(dependent)

    return resolved


def check_type(input, type_):
    """A permissice type checker/converter.

    :param input: What should be coverted.
    :param type_: Type that the input should be converted to
    :type type_: ``type``
    :return: input converted to :py:attr:`type_`
    """
    try:
        return type_(input)
    except TypeError:
        raise TypeError("Couldn't convert {} of type {} to {}".format(
            repr(input),
            type(input).__name__,
            type_.__name__
        ))


def count_elements(elem, doc, relevant_elems, register=None, scope=None):
    """Count elements by type.

    :param elem: The element that, if it is of any of the types in
                 :py:attr:`relevant_elems` will be counted.
    :type elem: :class:`panflute.base.Element`
    :param doc: The base document, used to store the current count.
    :type doc: :class:`panflute.elements.Doc`
    :param relevant_elems: A tuple of types that will be counted.
    :type relevant_elems: ``tuple``
    :param register: If ``None`` the default register will be used for
                     counting. Otherwise counting will happen in the register
                     provided here.
    :type register: ``str`` | ``None``
    :param scope: A tuple of this form (register, element that forms
                  the scope, levels to which will be counted)
    :type scope: ``tuple`` | ``None``

    >>> count_elements(
    ...     elem,
    ...     doc,
    ...     (panflute.Table,),
    ...     register='tables',
    ...     scope=('tables', (panflute.Header,), 2)
    ... )

    Will count Table elements relative to the current level 2 Header.
    """

    if scope is not None:
        if scope[0] is None:
            scope = (register, scope[1], scope[2])
        count_elements(elem, doc, scope[1], register=scope[0])
        if isinstance(scope[1], tuple):
            scope_type_name = ''.join(t.__name__ for t in scope[1])
        elif isinstance(scope[1], type):
            scope_type_name = scope[1].__name__

    if isinstance(relevant_elems, tuple):
        type_name = ''.join(t.__name__ for t in relevant_elems)
    elif isinstance(relevant_elems, type):
        type_name = relevant_elems.__name__

    if isinstance(elem, relevant_elems):

        if register is None:
            register = 'default'

        try:
            count_elems = doc.count_elems[register]
        except KeyError:
            doc.count_elems[register] = {
                type_name: [tuple(), 0]
            }
            count_elems = doc.count_elems[register]
        except AttributeError:
            doc.count_elems = {
                register: {
                    type_name: [tuple(), 0]
                }
            }
            count_elems = doc.count_elems[register]

        try:
            elem_counter = count_elems[type_name]
        except KeyError:
            elem_counter = [tuple(), 0]
            count_elems[type_name] = elem_counter

        index = 1 if not hasattr(elem, 'level') else elem.level

        if scope is not None:
            logging.debug(f'Scope Name is "{scope_type_name}"')
            current_level = get_elem_count(
                doc,
                scope_type_name,
                level=scope[2],
                register=scope[0])
            if current_level != elem_counter[0]:
                count_elems[type_name] = ([current_level]
                                          + [1] * (index - 1)
                                          + [0])

                elem_counter = count_elems[type_name]

        try:
            elem_counter[index] += 1
        except IndexError:
            for i in range(index - len(elem_counter)):
                elem_counter.append(1)
            elem_counter.append(1)
        del elem_counter[index+1:]


def get_elem_count(doc, types, level=1, register=None):
    """get_elem_count

    :param doc:
    :param types:
    :param level:
    :param register:
    """

    if isinstance(types, tuple):
        type_name = ''.join(t.__name__ for t in types)
    elif isinstance(types, str):
        type_name = types
    elif isinstance(types, type):
        logging.debug(f'Types is a type ({types}).')
        type_name = types.__name__
    else:
        raise TypeError('types should be either a touple of types a type or '
                        'a string')

    if register is None:
        register = 'default'

    try:
        count_elems = doc.count_elems[register]
        try:
            elem_counter = count_elems[type_name]
            try:
                current_level = tuple(elem_counter[1:level+1])
                scope = elem_counter[0]
            except IndexError:
                logging.debug('IndexError?')
                return (0,) * level

            if len(current_level) < level:
                logging.debug(f'Current level: {current_level};'
                              ' Scope: {scope}')
                current_level = (current_level
                                 + (1,) * (level - len(current_level)))

            return scope + current_level
        except KeyError:
            logging.debug(f"Didn't previously count that type ({type_name}).")
            count_elems[type_name] = [tuple(), 0]
            return (0,) * level

    except KeyError:
        logging.debug(f'Register empty ({register}).')

        doc.count_elems[register] = {
            type_name: [tuple(), 0]
        }
        return (0,) * level


def create_nested_tags(**kwargs):
    """Creates nested XML-tags from dictionary. If the dictionary contains a
    value for ``'contents'`` which should be a list of dictionaries then this
    function will be called recursively on these dictionaries and the returned
    tags will be appended to the root one.

    :param **kwargs: a dictionary with kwargs that will be passed to
                     :class:`bs4.elements.Tag`. It should at least
                     contain an entry for `name`
    """

    contents = None

    if 'contents' in kwargs:
        contents = kwargs['contents']
        del kwargs['contents']

    tag = bs4.element.Tag(**kwargs)
    if contents is not None:
        for c in contents:
            if isinstance(c, dict):
                tag.contents.append(create_nested_tags(**c))
            else:
                tag.contents.append(bs4.element.NavigableString(str(c)))

    return tag


def re_split(regex, string):
    """re_split

    :param regex: Regular expression object to use for the split.
                  Has to contain one capturing group
    :param string: String to split.

    yields tuples of strings, the second one being a match or None
    """
    if regex.search(string):

        split_list = regex.split(string)
        for n in range(0, len(split_list) // 2):
            yield (pf.Str(split_list.pop(0)), split_list.pop(0))

        yield (pf.Str(split_list.pop(0)), None)


def format_names(names):
    first = pf.Emph(pf.Str(split_name(names[0])[0]))
    if len(names) == 0:
        return [first]
    elif len(names) == 1:
        second = pf.Emph(pf.Str(split_name(names[0])[0]))
        return [first, pf.Str('and'), second]
    elif len(names) > 1:
        return [first, pf.Str('et al.')]


def split_name(name):
    parts = name.split(' ')
    parts = [p.strip(',. ') for p in parts]
    return parts


def panflute2output(elem, format='json', doc=None):
    if not isinstance(elem, (list, pf.ListContainer)):
        elem = [elem]

    if doc is None:
        doc = pf.Doc(*elem, format=format, api_version=(1, 17, 3, 1))
    else:
        doc = copy.deepcopy(doc)
        doc.format = format
        doc.api_version = (1, 17, 3, 1)

    with io.StringIO() as f:
        pf.dump(doc, f)
        ast = f.getvalue()

    if format == 'json':
        return ast
    else:
        return pf.run_pandoc(text=ast,
                             args=['-f', 'json', '-t', format, '--wrap=none'])


def uppercase_range(length):
    for i in range(length):
        yield number_to_uppercase(i)


def number_to_uppercase(number):
    number_of_uppercase_letters = len(string.ascii_uppercase)
    return ''.join(string.ascii_uppercase[i]
                   for i in num_to_base_tuple(number,
                                              number_of_uppercase_letters))


def num_to_base_tuple(number, base):
    collect = []
    while True:
        collect.append(number % base)
        if number // base == 0:
            break
        elif number // base >= base:
            number = number // base
            continue
        else:
            collect.append(number // base)
            break
    collect.reverse()
    return collect


def function_fron_dependencies(dependencies, *args):
    def function(*args):
        order = resolve_dependencies(dependencies)
        for action in order:
            action.object_(*args)

    return function
