#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

# Standard Library
import logging
import re

# Third Party
import panflute as pf

# This Module
from panscola import utils

logger = logging.getLogger(__name__)

aligned = re.compile(r"^\\begin{aligned}|\\end{aligned}$")


class MyMath(pf.Math):
    __slots__ = ["identifier", "classes", "attributes"]

    def __init__(
        self, text, format="DisplayMath", identifier="", classes=[], attributes={}
    ):
        super().__init__(text, format)
        self._set_ica(identifier, classes, attributes)


@utils.make_dependent()
def custom_display_math(elem, doc):
    if isinstance(elem, pf.Math) and elem.format == "Displaymath":
        new_elem = MyMath(elem.text, elem.format)

        return new_elem


def _frac(elem, doc):
    text = elem.text
    numerator, denominator, *rest = text.split("/")

    if rest:
        logger.debug(
            "Got a fraction with more than one slash, disregarding rest: %s", rest
        )

    if doc.format == "latex":
        return pf.RawInline(f"\\Tfrac{{{numerator}}}{{{denominator}}}", format="latex")


def _span(elem, doc):
    text = elem.text

    if doc.format == "latex":
        return pf.RawInline(f"{{{text}}}", format="latex")


ROLE_SHORTCUTS = {"frac": _frac, "span": _span}

pf.elements.RAW_FORMATS.update(ROLE_SHORTCUTS.keys())


@utils.make_dependent()
def role_shortcuts(elem, doc):
    if isinstance(elem, pf.RawInline) and elem.format in ROLE_SHORTCUTS:
        processing_function = ROLE_SHORTCUTS[elem.format]

        return processing_function(elem, doc)


@utils.make_dependent()
def math(elem, doc):
    attributes = getattr(elem, "attributes", {})
    label = attributes.get("label")

    utils.count_elements(
        elem,
        doc,
        (lambda x: isinstance(x, pf.Math) and x.format == "DisplayMath"),
        type_name="equation",
        register="equations",
        scope={"relevant_elems": pf.Header, "level": 1},
    )

    doc.equation_name = equation_name = label or ".".join(
        str(i) for i in utils.get_elem_count(doc, "equation", register="equations")
    )
    doc.equation_prefix = equation_prefix = utils.make_label(
        doc, "equa:{}".format(equation_name)
    )

    if (
        isinstance(elem, pf.Math)
        and elem.format == "DisplayMath"
        and doc.format == "latex"
    ):

        head = """\\begin{equa}
        \\eequabox{
        """
        tail = f"""
        }}{{
        $$
        {elem.text}
        $$
        }}
        \\end{{equa}}"""

        logger.debug(elem)

        caption = attributes.get("caption", "")
        caption_title = attributes.get("caption_title")

        caption_content = []

        if caption:
            caption_content = utils.make_caption(caption, caption_title)

        caption_content.append(
            pf.RawInline(f"\\label{{{equation_prefix}}}", format="latex")
        )

        return [
            pf.RawInline(head, format="latex"),
            *caption_content,
            pf.RawInline(tail, format="latex"),
        ]


@utils.make_dependent()
def _prepare(doc):
    pass


@utils.make_dependent()
def _finalize(doc):
    pass


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(math),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
