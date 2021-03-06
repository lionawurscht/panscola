#!/usr/bin/env python
"""Utility functions that are reused throughout the project."""
# Standard Library
import copy
import functools
import inspect
import io
import itertools as it
import logging
import reprlib
import string

# Third Party
import bs4
import panflute as pf
import pyparsing as pp

logger = logging.getLogger(__name__)


class Dependent:
    """A class to help manage dependencies within my filters.
    Classes that inherit from it are automatically created using the
    decorator :func:`make_dependent`. No instances of this class are
    usually created. Instead, calling it is equivalent to calling it's
    object.
    """

    _object = None
    _dependencies = []

    def __new__(cls, *args, **kwargs):
        return cls._object(*args, **kwargs)

    def __init__(self, _object=None, _dependencies=None):
        if _dependencies is not None:
            self._dependencies = check_type_strictly(_dependencies, list)

        if _object is not None:
            self._object = _object

    @classmethod
    def resolve_dependencies(cls, resolved=None, seen=None):
        """Calles the function :func:`resolve_dependencies` and returns
        its return value.

        :param resolved: list of :class:`Dependent` who's dependencies have
                         alredy been resolved.
        :type resolved: `list` | `None`
        :param seen: list or :class:`Dependent` that already appeared while
                     resolving its dependencies. Helps avoid circular
                     dependencies.
        :type seen: `list` | `None`
        """

        return resolve_dependencies(cls, resolved, seen)

    @classmethod
    def __repr__(cls):
        if hasattr(cls._object, "__name__"):
            return cls._object.__name__
        else:
            return repr(cls._object)

    @classmethod
    def add_dependency(cls, dependency):
        cls._dependencies.append(dependency)

    @classmethod
    def add_dependencies(cls, *dependencies):
        for dependency in dependencies:
            cls.add_dependency(dependency)

    @classmethod
    def to_function(cls):
        actions, _ = cls.resolve_dependencies()

        def run_functions(*args):
            for a in actions:
                a._object(*args)

        return run_functions


def resolve_dependencies(dependent, resolved=None, seen=None):
    """Resolve all the dependencies of a Class or Instance of a Class that
    inherited from :class:`Dependent`

    :param resolved: list of :class:`Dependent` who's dependencies have
                        alredy been resolved.
    :type resolved: `list` | `None`
    :param seen: list or :class:`Dependent` that already appeared while
                    resolving its dependencies. Helps avoid circular
                    dependencies.
    :type seen: `list` | `None`
    :returns: a `tuple` of containing the list of resolved and seen
             :class:`Dependent` objects.
    """

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

            for dependency in dependent._dependencies:
                if dependency not in resolved:
                    if dependency in seen:
                        raise Exception("Circular dependency")
                    resolve_dependencies(dependency, resolved, seen)
            resolved.append(dependent)

    return resolved, seen


def make_dependent(*dependencies):
    """A decorator to make a function into a Class that inherits from
    :class:`Dependent`.

    :param *dependencies: What other functions this one is dependent on.
    :type dependencies: :class:`Dependent` sequence

    .. code-block:: python

        @make_dependent()
        def a_func(name):
            print(name)

        @make_dependent(a_func)
        def b_func(name):
            print(name)

    Now `b_func` is dependent on `a_func`. A list of dependent functions can
    then be created doing this:

    .. code-block:: python

        b_func.resolve_dependencies()
    """

    def function_wrapper(func):
        inner_dependencies = dependencies

        class Wrapped(Dependent):
            _object = func
            _dependencies = inner_dependencies

        # Make the wrapped class have the original functions attributed

        for attr in functools.WRAPPER_ASSIGNMENTS:
            try:
                setattr(Wrapped, attr, getattr(func, attr))
            except AttributeError:
                logger.debug("Couldn't set attributes %s of %s", attr, Wrapped)

        doc = getattr(func, "__doc__", "")
        doc = "" if doc is None else doc

        signature = str(inspect.signature(func))

        name_form = func

        name = getattr(func, "__name__", None)

        if name is None:
            try:
                name = func.__class__.__name__
            except AttributeError:
                pass

        doc = f"{name}{signature}\n" + doc
        setattr(Wrapped, "__doc__", doc)

        return Wrapped

    return function_wrapper


def reduce_dependencies(*list_):
    """Tries to resolve all the dependencies passed as parameters.

    :param *list_: The dependencies that sould be resolved
    :type *list: `tuple` of `Dependent`
    :returns: A list of functions, hopefully in the order of their
              depencency.
    """

    return [
        i._object
        for i in functools.reduce(reduce_dependencies_helper, [None] + list(list_))[0]
    ]


def reduce_dependencies_helper(returned_value, dependent):
    """Just a helper function for :func:`reduce_dependencies`.

    :param returned_value: The tuple returned by
                           :func:`~panscola.Dependent.resolve_dependencies`
    :type returned_value: `tuple` of two `list`
    :param dependent:
    """

    if returned_value is None:
        returned_value = ([], [])

    return_value = dependent.resolve_dependencies(*returned_value)

    return return_value


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
        raise TypeError(
            "Couldn't convert {} of type {} to {}".format(
                repr(input), type(input).__name__, type_.__name__
            )
        )


def check_type_strictly(input, type_):
    if isinstance(input, type_):
        return input
    else:
        raise TypeError(
            "Expected input to be of type {}, was {}.".format(type_, type(input))
        )


_enclosed = pp.Forward()
_nestedParens = pp.nestedExpr(opener="(", closer=")", content=_enclosed)
_nestedBrackets = pp.nestedExpr(opener="[", closer="]", content=_enclosed)

_enclosed << (
    pp.delimitedList(
        pp.pyparsing_common.number
        | pp.QuotedString('"')
        | pp.QuotedString("'")
        | _nestedParens
        | _nestedBrackets
    )
    | _nestedParens
    | _nestedBrackets
)

_key = pp.Word(pp.alphas) + pp.Suppress("=")
_dict_value = _enclosed + (pp.Suppress(",") | pp.Suppress(pp.SkipTo(")")))

_args = pp.Optional(pp.delimitedList(_enclosed)).setResultsName("args") + (
    pp.Suppress(",") | pp.Suppress(pp.SkipTo(_key)) | pp.Suppress(pp.SkipTo(")"))
)

_kwargs = pp.Optional(pp.dictOf(_key, _dict_value)).setResultsName("kwargs")

_parameters = pp.Suppress("(").leaveWhitespace() + _args + _kwargs + pp.Suppress(")")

_function = (
    pp.Suppress("::")
    + pp.Word(pp.alphas).leaveWhitespace().setResultsName("name", listAllMatches=True)
    + _parameters
)


def options(elem, doc, **kwargs):
    return None, kwargs


def box(elem, doc, repeat):
    return "[]" * repeat, None


functions = {"options": options, "box": box}


def run_functions(elem, doc):
    string_ = pf.stringify(elem)
    parts = []
    returned_values = []

    for string_, function in parse_functions(string_):
        parts.append(string_)

        if function is not None:
            try:
                load_function = functions[function[0]]
                args = function[1]
                kwargs = function[2]
                new_string, return_dict = load_function(elem, doc, *args, **kwargs)

                if return_dict is not None:
                    returned_values.append(return_dict)

                if new_string is not None:
                    parts.append(new_string)
                    print(return_dict)
            except KeyError:
                pass
    print(pf.convert_text("".join(parts), input_format="rst")[0])
    print({k: v for x in returned_values for k, v in x.items()})


def parse_functions(string):
    last_end = 0

    for token, start, end in _function.scanString(string):
        print(token)
        head = string[last_end:start]
        name = token["name"][0]
        kwargs = token.get("kwargs", None)
        kwargs = {} if kwargs is None else kwargs.asDict()

        args = token.get("args", None)
        args = [] if args is None else args.asList()

        yield head, (name, args, kwargs)

        last_end = end

    tail = string[last_end:-1]
    yield tail, None


def _get_type_name_checker(relevant_elems, type_name=None, **kwargs):
    if isinstance(relevant_elems, tuple):
        type_name = "".join(t.__name__ for t in relevant_elems)

        def checker(elem):
            return isinstance(elem, relevant_elems)

    elif isinstance(relevant_elems, type):
        type_name = relevant_elems.__name__

        def checker(elem):
            return isinstance(elem, relevant_elems)

    elif isinstance(relevant_elems, str):
        type_name = relevant_elems
        checker = None
    elif callable(relevant_elems):
        type_name = type_name or relevant_elems.__name__
        checker = relevant_elems
    else:
        raise TypeError(
            f"relevant_elems should be tuple, type of tuples of a callable, got: {type(relevant_elems)}: {relevant_elems}"
        )

    return checker, type_name


def count_elements(
    elem, doc, relevant_elems, register=None, scope=None, type_name=None, **kwargs
):
    """Count elements by type. Put this in the beginning of a walk function
    before checking any type to keep track of the current element counts.

    :param elem: The element that, if it is of any of the types in
                 :py:attr:`relevant_elems` will be counted.
    :type elem: :class:`panflute.base.Element`
    :param doc: The base document, used to store the current count.
    :type doc: :class:`panflute.elements.Doc`
    :param relevant_elems: A tuple of types that will be counted or a function
                           that returns true then an element should be counted
    :type relevant_elems: ``tuple`` | callable
    :param register: If ``None`` the default register will be used for
                     counting. Otherwise counting will happen in the register
                     provided here.
    :type register: ``str`` | ``None``
    :param scope: A tuple of this form (register, element that forms
                  the scope, levels to which will be counted)
    :type scope: ``tuple`` | ``None``
    :param type_name: A name to give the type, used only when
                      ``relevant_elems`` is a function.

    >>> count_elements(
    ...     elem,
    ...     doc,
    ...     (panflute.Table,),
    ...     register='tables',
    ...     scope=('tables', (panflute.Header,), 2)
    ... )

    Will count Table elements relative to the current level 2 Header.
    """

    if register is None:
        register = "default"

    if scope is not None:
        scope.setdefault("register", register)

        count_elements(elem, doc, **scope)

        __, scope_type_name = _get_type_name_checker(**scope)

    checker, type_name = _get_type_name_checker(relevant_elems, type_name)

    if checker(elem):
        try:
            count_elems = doc.count_elems[register]
        except KeyError:
            doc.count_elems[register] = count_elems = {type_name: [tuple(), 0]}
        except AttributeError:
            doc.count_elems = {register: {type_name: [tuple(), 0]}}
            count_elems = doc.count_elems[register]

        try:
            elem_counter = count_elems[type_name]
        except KeyError:
            elem_counter = [tuple(), 0]
            count_elems[type_name] = elem_counter

        index = 1 if not hasattr(elem, "level") else elem.level

        if scope is not None:
            current_level = get_elem_count(doc, **scope)

            if current_level != elem_counter[0]:
                count_elems[type_name] = [current_level] + [1] * (index - 1) + [0]

                elem_counter = count_elems[type_name]

        try:
            elem_counter[index] += 1
        except IndexError:
            for i in range(index - len(elem_counter)):
                elem_counter.append(1)
            elem_counter.append(1)
        del elem_counter[index + 1 :]


def make_label(doc, label):
    doc.link_targets.add(label)

    return label


def get_elem_count(
    doc, relevant_elems, level=1, register=None, type_name=None, **kwargs
):
    """get_elem_count

    :param doc:
    :param types:
    :param level:
    :param register:
    """

    __, type_name = _get_type_name_checker(relevant_elems, type_name)

    if register is None:
        register = "default"

    try:
        count_elems = doc.count_elems[register]
        try:
            elem_counter = count_elems[type_name]
            try:
                current_level = tuple(elem_counter[1 : level + 1])
                scope = elem_counter[0]
            except IndexError:
                return (0,) * level

            if len(current_level) < level:
                current_level = current_level + (1,) * (level - len(current_level))

            return scope + current_level
        except KeyError:
            count_elems[type_name] = [tuple(), 0]

            return (0,) * level

    except KeyError:
        doc.count_elems[register] = {type_name: [tuple(), 0]}

        return (0,) * level


def create_nested_tags(**kwargs):
    """Creates nested :class:`~bs4.element.Tag` from dictionary. The
    dictionary may contain a value for the key `contents`.  This should
    be a list of
    dictionaries or strings.
    Dictionaries will be processed recursively and the returnes tag will
    be appeneded to the parent tag.  Strings will be made a
    :class:`~bs4.element.NavigableString` and appended to the parent tag.

    :param **kwargs: a dictionary with kwargs that will be passed to
                     :class:`~bs4.elements.Tag`. It should at least
                     contain a value for the key `name`
    """

    contents = None

    if "contents" in kwargs:
        contents = kwargs["contents"]
        del kwargs["contents"]

    tag = bs4.element.Tag(**kwargs)

    if contents is not None:
        for c in contents:
            if isinstance(c, dict):
                tag.contents.append(create_nested_tags(**c))
            elif isinstance(c, bs4.element.Tag):
                tag.contents.append(c)
            else:
                tag.contents.append(bs4.element.NavigableString(str(c)))

    return tag


def soup_to_string(soup, seperator=""):
    return seperator.join(s.prettify() for s in soup.contents)


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

        return [first, pf.Str("and"), second]
    elif len(names) > 1:
        return [first, pf.Str("et al.")]


def split_name(name):
    parts = name.split(" ")
    parts = [p.strip(",. ") for p in parts]

    return parts


def panflute2output(elem, format="json", doc=None):
    if not isinstance(elem, (list, pf.ListContainer)):
        elem = [elem]

    if doc is None:
        doc = pf.Doc(*elem, format=format, api_version=(1, 17, 3, 1))
    else:
        doc = copy.deepcopy(doc)
        doc.content = elem
        doc.format = format
        doc.api_version = (1, 17, 3, 1)

    with io.StringIO() as f:
        pf.dump(doc, f)
        ast = f.getvalue()

    if format == "json":
        return_value = ast
    else:
        return_value = pf.run_pandoc(
            text=ast, args=["-f", "json", "-t", format, "--wrap=none"]
        )

    return return_value


def uppercase_range(length):
    for i in range(length):
        yield number_to_uppercase(i)


def number_to_uppercase(number):
    number_of_uppercase_letters = len(string.ascii_uppercase)

    return "".join(
        string.ascii_uppercase[i]
        for i in num_to_base_tuple(number, number_of_uppercase_letters)
    )


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


false_strings = ("False", "false", "no", "No", "n", "N")
true_strings = ("True", "true", "yes", "Yes", "y", "Y")


def string_to_bool(
    string, default=False, true_strings=true_strings, false_strings=false_strings
):
    if string in false_strings:
        return False
    elif string in true_strings:
        return True
    else:
        return default


numeric = "0123456789-."


def string_to_float_unit(string):
    string = string.strip()

    for i, c in enumerate(string):
        if c not in numeric:
            break
    try:
        number = string[:i]
        number = number.strip()
        number = float(string[:i])
    except ValueError:
        raise ValueError(
            f"Could not convert: {number!r} to float. " f"Original string: {string!r}"
        )
    unit = string[i:]
    unit = unit.strip()

    return number, unit


def test():
    """test(name)
    aber aber aber
    """
    pass


def reverse_walk(elem, action, doc=None):
    # Infer the document thanks to .parent magic

    if doc is None:
        doc = elem.doc

    # First apply the action to the element
    altered = action(elem, doc)

    # Then iterate over children

    for child in elem._children:
        obj = getattr(elem, child)

        if isinstance(obj, pf.Element):
            ans = reverse_walk(obj, action, doc)
        elif isinstance(obj, pf.ListContainer):
            ans = (reverse_walk(item, action, doc) for item in obj)
            # We need to convert single elements to iterables, so that they
            # can be flattened later
            ans = ((item,) if type(item) != list else item for item in ans)
            # Flatten the list, by expanding any sublists
            ans = list(it.chain.from_iterable(ans))
        elif isinstance(obj, pf.DictContainer):
            ans = [(k, reverse_walk(v, action, doc)) for k, v in obj.items()]
            ans = [(k, v) for k, v in ans if v != []]
        elif obj is None:
            pass  # Empty table headers or captions
        else:
            raise TypeError(type(obj))
        setattr(elem, child, ans)

    return elem if altered is None else altered


def make_inline(text):
    if not text:
        return text

    if isinstance(text, str):
        text = f"""
.. role:: latex(raw)
   :format: latex

{text}
"""
        text = pf.convert_text(text, input_format="rst")

    if not isinstance(text, (list, pf.ListContainer)):
        text = [text]

    text = [pf.Span(*cc.content) if isinstance(cc, (pf.Block)) else cc for cc in text]

    return text


def make_caption(caption_text, caption_title, subcaption=False):
    caption_text = make_inline(caption_text)

    caption_command = "subcaption" if subcaption else "caption"

    caption_head = [pf.RawInline(f"\\{caption_command}{{", format="latex")]

    if caption_title:
        caption_title = make_inline(caption_title)
        caption_head = [
            pf.RawInline(f"\\{caption_command}[", format="latex"),
            *caption_title,
            pf.RawInline("]{", format="latex"),
        ]

    caption_tail = "}"

    return [*caption_head, *caption_text, pf.RawInline(caption_tail, format="latex")]


def patch_elem_type(elem_type):
    class patched(elem_type):
        __slots__ = list(elem_type.__slots__) + ["attributes"]
        _original_type = elem_type

        @property
        def tag(self):
            tag = self._original_type.__name__
            return tag

        def to_json(self):
            # We need to get rid of this, in particular if we stored other
            # elements in here.
            # Maybe an alternative would be to use "_attributes" instead and
            # make "attributes" a property?

            delattr(self, "attributes")
            return super().to_json()

        @reprlib.recursive_repr()
        def __repr__(self):
            return super().__repr__()

    patched.__name__ = "{}Patched".format(elem_type.__name__)

    return patched


def new_elem_from_old(old_elem, new_elem_type):
    kwargs = {
        s: getattr(old_elem, s)
        for s in old_elem.__slots__
        if not s.startswith("_") and s not in ("rows", "cols")
    }
    children = getattr(old_elem, "_children", [])
    kwargs.update({c: getattr(old_elem, f"_{c}") for c in children if c != "content"})
    args = []

    if "content" in children:
        args = old_elem.content

    return new_elem_type(*args, **kwargs)


_PATCHED_ELEMS = {}


def add_attributes(attributes, force_for=None):
    force_for = force_for or tuple()

    def _add_attributes(elem, doc):
        if type(elem) in force_for:
            if isinstance(elem, pf.Table):
                logger.debug("===== Got a table with this header: %s", elem.header)

            new_elem_type = _PATCHED_ELEMS.setdefault(
                type(elem), patch_elem_type(type(elem))
            )

            elem = new_elem_from_old(elem, new_elem_type)
            elem.attributes = {}

        if hasattr(elem, "identifier") and "identifier" in attributes:
            elem.identifier = attributes.pop("identifier")

        if hasattr(elem, "attributes"):
            elem.attributes.update(attributes)

        return elem

    return _add_attributes


def transform_attributes(attributes):
    def _transform_attributes(elem, doc):
        if hasattr(elem, "attributes"):
            for attribute, (transformer, default) in attributes.items():
                if attribute in elem.attributes:
                    elem.attributes[attribute] = transformer(elem.attributes[attribute])
                else:
                    elem.attributes[attribute] = default

        return elem

    return _transform_attributes


def rm_attributes(*attributes):
    logger.debug(attributes)

    def _rm_attributes(elem, doc):
        if hasattr(elem, "attributes"):
            for attr in attributes:
                try:
                    elem.attributes.pop(attr)
                except KeyError:
                    pass

    return _rm_attributes


class _BeforeAction:
    def __init__(self, function, args=None, kwargs=None):
        self.func = function
        self.args = args or tuple()
        self.kwargs = kwargs or {}

    def partial(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def get_copy(self, *args, **kwargs):
        return _BeforeAction(self.func, self.args, self.kwargs)

    def do_before(self, *args, **kwargs):
        self.gen = self.func(*self.args, *args, **self.kwargs, **kwargs)

        try:
            next(self.gen)
        except StopIteration:
            logger.warning(
                "This shouldn't happen, a before_function apparently doesn't yield."
            )
            pass

    def __call__(self, *args, **kwargs):
        try:
            return next(self.gen)
        except StopIteration:
            return


def before_action(action):
    new_action = _BeforeAction(action)

    return new_action


@make_dependent()
@before_action
def testaction(elem, doc):

    yield

    yield


def walk(self, action, doc=None):
    if doc is None:
        doc = self.doc

    if isinstance(action, _BeforeAction):
        action = action.get_copy()
        action.do_before(self, doc)

    return self._walk(action, doc)


pf.Element._walk = pf.Element.walk
pf.Element.walk = walk


def doc_format(format_):
    def for_format(fn):
        format__ = format_

        @functools.wraps(fn)
        def wrapped(elem, doc, *args, **kwargs):
            if doc.format == format__:
                return_value = fn(elem, doc, *args, **kwargs)
                return return_value

        return wrapped

    return for_format


def run_filters(
    actions,
    prepare=None,
    finalize=None,
    input_stream=None,
    output_stream=None,
    doc=None,
    **kwargs,
):

    load_and_dump = doc is None

    if load_and_dump:
        doc = pf.load(input_stream=input_stream)

    if prepare is not None:
        prepare(doc)

    for action in actions:
        if kwargs:
            if isinstance(action, _BeforeAction):
                action.partial(**kwargs)
            else:
                action = functools.partial(action, **kwargs)

        doc = doc.walk(action, doc)

    if finalize is not None:
        finalize(doc)

    if load_and_dump:
        pf.dump(doc, output_stream=output_stream)
    else:
        return doc


pf.run_filters = run_filters


def main():
    @make_dependent()
    def popel(name):
        """A simple function.

        :param name:
        """
        print(name)

    print(type(popel))
    print(popel("Lion"))
    print(popel.to_function())
    print(reduce_dependencies(popel))


if __name__ == "__main__":
    main()
