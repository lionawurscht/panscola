#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

# Standard Library
import copy
import itertools as it
import logging
import pprint

# Third Party
import panflute as pf
import regex as re
from bs4 import BeautifulSoup

# This Module
from panscola import (abbreviations, boxes, citations, figure, mathfilter,
                      process_headers, table, utils)

logger = logging.getLogger(__name__)


def check_group(value, group):
    if value not in group:
        tag = type(value).__name__
        msg = "element {}: {} not in group {}".format(tag, value, repr(group))
        raise TypeError(msg)
    else:
        return value


pf.utils.check_group = check_group

# For pretty printing dicts
pp = pprint.PrettyPrinter(indent=4)

print_ = print


def print(*x):
    pf.debug(*(pp.pformat(p) for p in x))


"""Make toc-title a raw inline for odt"""


@utils.make_dependent()
def repair_toc_title(elem, doc):
    if doc.format == "odt" and isinstance(elem, pf.MetaMap):
        for key, value in elem.content.items():
            string = pf.stringify(value).strip()

            if key == "toc-title":
                raw = pf.RawBlock(string, format="opendocument")
                elem[key] = pf.MetaBlocks(raw)


"""Add attributes of a class called 'attributed' to all its children."""


@utils.make_dependent()
def attributed(elem, doc):
    if isinstance(elem, pf.Div) and "attributed" in elem.classes:
        attributes = elem.attributes
        utils.reverse_walk(
            elem, utils.add_attributes(attributes, force_for=[pf.Math, pf.Table])
        )


"""Comment out parts of the document
Start comments with '::comment-begin' as a seperate paragraph and end it
likewise with '::comment-end'
"""


@utils.make_dependent()
def comment(elem, doc):
    text = pf.stringify(elem).strip()
    is_relevant = isinstance(elem, pf.Str) and text.startswith("::comment-")

    if is_relevant and text.endswith("-begin"):
        doc.ignore += 1

        # comment text wont be displayed

        if doc.show_comments and doc.ignore == 1:
            logger.debug("Seems like show_comments is set to true?")

            return pf.Emph(pf.Str("Comment:"))

        return []

    if doc.ignore > 0:
        if is_relevant and text.endswith("-end"):
            doc.ignore -= 1
        elif doc.show_comments:
            return None

        return []


@utils.make_dependent()
def comment(elem, doc):
    text = pf.stringify(elem).strip()
    is_relevant = isinstance(elem, pf.Str) and text.startswith("::comment-")

    if is_relevant and text.endswith("-begin"):
        doc.ignore += 1

        # comment text wont be displayed

        if doc.show_comments and doc.ignore == 1:
            logger.debug("Seems like show_comments is set to true?")

            return pf.Emph(pf.Str("Comment:"))

        return []

    if doc.ignore > 0:
        if is_relevant and text.endswith("-end"):
            doc.ignore -= 1
        elif doc.show_comments:
            return None

        return []


@utils.make_dependent()
def alteration(elem, doc):
    text = pf.stringify(elem).strip()
    is_relevant = isinstance(elem, pf.Para) and text.startswith("::alteration-")

    if not is_relevant:
        return

    if text.endswith("-begin"):
        return pf.RawBlock("{\\color{alterationcolor}", format="latex")

    if text.endswith("-end"):
        return pf.RawBlock("}", format="latex")


hyphenation_suggestion = re.compile(r"\\\-")


@utils.make_dependent()
def suggest_hyphenations(elem, doc):
    if isinstance(elem, pf.Str) and hyphenation_suggestion.search(elem.text):
        parts = [pf.Str(part) for part in hyphenation_suggestion.split(elem.text)]
        parts = [
            part
            for pair in it.zip_longest(
                parts, [pf.RawInline("\\-", format="latex")] * (len(parts) - 1)
            )
            for part in pair
            if part is not None
        ]

        return parts


"""Rendering my Tables"""


def check_type(input, type_):
    try:
        return type_(input)
    except TypeError:
        raise TypeError(
            "Couldn't convert {} of type {} to {}".format(
                repr(input), type(input).__name__, type_.__name__
            )
        )


class Table(pf.Table):
    def __init__(self, *args, col_cnt=None, row_cnt=None, total_width=0.8, **kwargs):
        super().__init__(*args, **kwargs)

        self.col_cnt = check_type(col_cnt, int)
        self.row_cnt = check_type(row_cnt, int)
        self.total_width = check_type(total_width, float)


class TableCell(pf.TableCell):
    def __init__(
        self,
        *args,
        col_span=1,
        row_span=1,
        covered=False,
        rm_horizontal_margins=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.col_span = check_type(col_span, int)
        self.row_span = check_type(row_span, int)
        self.covered = check_type(covered, bool)
        self.rm_horizontal_margins = check_type(rm_horizontal_margins, bool)


class TableRow(pf.TableRow):
    def __init__(
        self, *args, underlines=None, top_space=False, btm_space=False, **kwargs
    ):

        super().__init__(*args, **kwargs)

        self.underlines = (
            [] if underlines is None else pf.utils.check_type(underlines, list)
        )
        self.top_space = check_type(top_space, bool)
        self.btm_space = check_type(btm_space, bool)


def custom_table(elem, doc):
    if isinstance(elem, pf.Div) and "table" in elem.classes:
        if "caption" in elem.attributes:
            doc.current_caption = elem.attributes["caption"]
        else:
            doc.current_caption = None

        elem.walk(raw_to_custom_table)


def raw_to_custom_table(elem, doc):
    if isinstance(elem, pf.RawBlock):
        table_matrix = xml_to_table_matrix(elem.text)
        table_pf = table_matrix_to_pf(table_matrix, doc)
        table_pf = table_pf.walk(table_links)

        return table_pf


def xml_to_table_matrix(xml_input):
    table_soup = BeautifulSoup(xml_input, "xml")

    rows = []

    for row in table_soup.table.find_all("row"):
        row_attributes = row.attrs
        row_attributes["underlines"] = [
            tuple(check_type(i, int) for i in u.strip().split("-"))
            for u in row_attributes.get("underlines", "").split(",")
            if u
        ]

        cells = []

        for cell in row.find_all("cell"):
            cell_attributes = cell.attrs
            cell_content = "".join(str(c) for c in cell.contents)

            if cell_attributes:
                cells.append(((cell_content,), cell_attributes))
            else:
                cells.append(cell_content)

        rows.append([tuple(cells), row_attributes])

    footnotes = []

    for f in table_soup.table.find_all("footnotes"):
        footnotes.append("".join(str(c) for c in f.contents))

    return [rows, "\n".join(footnotes)]


str_is_table_link = re.compile(r"\[\^((?:[^\s\[\]]+),?)+\]_")


def table_links(elem, doc):
    if isinstance(elem, pf.Str):
        text = pf.stringify(elem)

        if str_is_table_link.search(text):
            label = str_is_table_link.search(text).group(1)

            return pf.Link(pf.Str(label), url=label, classes=["table_note"])


def table_matrix_to_pf(matrix, doc):
    table = matrix[0]
    footnotes = [i for i in list_to_elems([matrix[1]])]

    row_cnt = len(table)

    rows = []
    new_col_cnt = 0
    old_col_cnt = None

    for r, row in enumerate(table):
        cells = []
        r_kwargs = row[1]

        for c, cell in enumerate(row[0]):
            new_col_cnt += 1

            if isinstance(cell, tuple):
                c_args = cell[0]
                c_kwargs = cell[1]

                col_span = check_type(c_kwargs.get("col_span", 1), int)

                cells.append(TableCell(*list_to_elems(c_args), **c_kwargs))

                for i in range(1, col_span):
                    new_col_cnt += 1
                    cells.append(TableCell(pf.Null(), covered=True))
            else:
                cells.append(TableCell(*list_to_elems([cell])))

        if old_col_cnt is None:
            old_col_cnt = new_col_cnt

        if new_col_cnt != old_col_cnt:
            raise IndexError(
                f"Expected {old_col_cnt} columns " f"but got {new_col_cnt} in {row}"
            )

        new_col_cnt = 0

        rows.append(TableRow(*cells, **r_kwargs))

    t_kwargs = {}

    if doc.current_caption:
        t_kwargs["caption"] = [pf.Span(pf.Str(doc.current_caption))]

    return pf.Div(
        Table(*rows, col_cnt=old_col_cnt, row_cnt=row_cnt, **t_kwargs),
        *footnotes,
        classes=["custom_table"],
    )


def list_to_elems(list_):
    for i in list_:
        if isinstance(i, str):
            for e in pf.convert_text(i, "rst"):
                yield e
        else:
            yield pf.Plain(pf.Str(str(i)))


def _get_ref(url, doc):
    ref = None

    if url in doc.labels:
        ref = doc.labels[url]
        logger.debug("Found url: %s in labels: %s", url, ref)
    elif url in doc.link_targets:
        ref = url

    return ref


@utils.make_dependent()
def gather_link_targets(elem, doc):
    if isinstance(elem, pf.Header):
        doc.labels[f"#{elem.identifier}"] = elem.identifier


@utils.make_dependent()
def render_links(elem, doc):
    if isinstance(elem, pf.Link) and doc.format == "latex":
        url = elem.url

        ref = _get_ref(url, doc)

        head = "\\myref{{{ref}}}"
        tail = ""

        if ref:
            if elem.content:
                head = "\\myref{{{ref}}}["
                tail = "]"

            return [
                pf.RawInline(head.format(ref=ref), format="latex"),
                *elem.content,
                pf.RawInline(tail, format="latex"),
            ]

        alt_url = pf.stringify(elem).strip()
        ref = _get_ref(alt_url, doc)

        if ref:
            return [
                pf.RawInline(head.format(ref=ref), format="latex"),
                pf.RawInline(tail, format="latex"),
            ]

        logger.debug(url)


@utils.make_dependent(
    process_headers._prepare,
    table._prepare,
    citations._prepare,
    abbreviations._prepare,
    boxes._prepare,
    mathfilter._prepare,
    figure._prepare,
)
def _prepare(doc):
    # for the comment filter
    doc.show_comments = doc.get_metadata("show-comments", False)

    logger.debug(
        "Show comments is: {}, type({})".format(
            doc.show_comments, type(doc.show_comments)
        )
    )

    doc.ignore = 0
    doc.link_targets = set()

    if not hasattr(doc, "labels"):
        doc.labels = dict()


@utils.make_dependent(
    process_headers._finalize,
    table._finalize,
    citations._finalize,
    abbreviations._finalize,
    boxes._finalize,
    mathfilter._finalize,
)
def _finalize(doc):
    # Add headings for the abstracts

    if doc.format != "latex":
        for name in ["abstract", "secondabstract"]:
            abstract = doc.metadata.content.get(name, None)
            abstract_name = doc.get_metadata(f"{name}name", name.capitalize())

            if abstract:
                abstract.walk(mathfilter.role_shortcuts)
                title = pf.Header(pf.Str(abstract_name), level=4)
                doc.metadata[name].content.list.insert(0, title)


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(
            utils.testaction,
            process_headers.process_headers,
            comment,
            alteration,
            suggest_hyphenations,
            attributed,
            table.xml_code_to_table,
            citations.parse_citations,
            abbreviations.parse_abbreviations,
            boxes.boxes,
            mathfilter.role_shortcuts,
            mathfilter.math,
            figure.figure,
            figure.render_float_rows,
            figure.correct_image_paths,
            figure.clean_multicolumn,
            figure.table_links,
            citations.render_citations,
            abbreviations.render_abbreviations,
            table.render_table,
            gather_link_targets,
            render_links,
            repair_toc_title,
        ),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
