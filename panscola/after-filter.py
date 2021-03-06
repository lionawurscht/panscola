#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

# Third Party
import panflute as pf

# This Module
from panscola import utils


def check_group(value, group):
    if value not in group:
        tag = type(value).__name__
        msg = "element {}: {} not in group {}".format(tag, value, repr(group))
        raise TypeError(msg)
    else:
        return value


pf.utils.check_group = check_group
pf.elements.check_group = check_group


@utils.make_dependent()
def fix_appendix(elem, doc):
    """Looks for headings titled 'Bibliography' or 'Abbreviations',
    adds a page break before them and puts them at the end of the
    documents.

    :param elem:
    :param doc:
    """

    if isinstance(elem, pf.Header) and pf.stringify(elem) in (
        "Bibliography",
        "Abbreviations",
    ):
        list_ = (
            doc.abbreviations
            if pf.stringify(elem) == "Abbreviations"
            else doc.bibliography
        )

        elem.classes.append("page-break-before")

        list_.append(elem)
        next_ = elem.next

        while True:
            next = next_

            if (
                isinstance(next, pf.Header) and next.level == elem.level
            ) or next is None:
                break
            else:
                next_ = next.next
                list_.append(next)
                next.parent.content.pop(next.index)

                return []


html_formats = ("html", "html5")


def render_page_break_before(elem, doc):
    if hasattr(elem, "classes") and "page-break-before" in elem.classes:
        elem.classes.remove("page-break-before")
        index = elem.index

        if isinstance(elem, pf.Block):
            raw_builder = pf.RawBlock
        elif isinstance(elem, pf.Inline):
            raw_builder = pf.RawInline

        raw = None

        if doc.format == "latex":
            raw = raw_builder("\\clearpage", format="latex")
        elif doc.format == "odt":
            raw = raw_builder(
                '<text:p text:style-name="Break_20_Before" />', format="opendocument"
            )

        if raw is not None:
            elem.parent.content.insert(index + 1, raw)
            elem.parent.content.insert(index + 2, elem)

            return []


@utils.make_dependent()
def _prepare(doc):
    doc.abbreviations = []
    doc.bibliography = []


@utils.make_dependent()
def _finalize(doc):
    doc.content.extend(doc.bibliography)
    doc.content.extend(doc.abbreviations)

    doc.walk(render_page_break_before)


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(fix_appendix),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
