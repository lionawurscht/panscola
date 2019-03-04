#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

# Standard Library
import logging
import re
import unicodedata
from collections import defaultdict

# Third Party
import panflute as pf

# This Module
from panscola import utils

logger = logging.getLogger(__name__)


@utils.make_dependent()
def _prepare(doc):
    doc.count_elems = defaultdict(dict)


@utils.make_dependent()
def parse_float_rows(elem, doc):
    if isinstance(elem, pf.Div):
        if "floatrow" in elem.classes:
            utils.reverse_walk(elem, utils.add_attributes({"float_row": elem}))
        elif "subfloatrows" in elem.classes:
            attributes = getattr(elem, "attributes", {})

            child_attributes = {"sub_float_rows": elem}
            utils.reverse_walk(elem, utils.add_attributes(child_attributes))

            cols = attributes.get("cols")

            if cols is not None:
                rel_width = 1 / float(cols)
                utils.reverse_walk(
                    elem,
                    utils.transform_attributes(
                        {"width": (lambda w: float(w) * rel_width, rel_width)}
                    ),
                )


def _is_figure_or_subfloatrow(elem):
    return (isinstance(elem, pf.Div) and "sub_float_rows" in elem.classes) or (
        isinstance(elem, pf.Image)
        and "sub_float_rows" not in getattr(elem, "attributes", {})
    )


@utils.make_dependent(parse_float_rows)
@utils.before_action
def figure(elem, doc):
    attributes = getattr(elem, "attributes", {})
    label = attributes.get("label")
    float_row = attributes.get("float_row", None)
    sub_float_rows = attributes.get("sub_float_rows", None)

    utils.count_elements(
        elem,
        doc,
        lambda e: isinstance(e, pf.Image)
        and "sub_float_rows" in getattr(e, "attributes", {}),
        type_name="subfigures",
        register="figures",
        scope={
            "relevant_elems": _is_figure_or_subfloatrow,
            "type_name": "figures_and_subfloatrows",
            "level": 1,
            "scope": {"relevant_elems": pf.Header, "level": 1},
        },
    )

    yield

    doc.figure_name = figure_name = label or ".".join(
        str(i)
        for i in utils.get_elem_count(
            doc,
            "figures_and_subfloatrows" if sub_float_rows is None else "subfigures",
            register="figures",
        )
    )
    doc.figure_prefix = figure_prefix = utils.make_label(
        doc, "fig:{}".format(figure_name)
    )

    if isinstance(elem, pf.Image):
        url = getattr(elem, "url", "")
        use_input = any(url.endswith(s) for s in (".pgf", ".pdf_tex"))

        if doc.format == "latex":

            for fr in (sub_float_rows, float_row):
                if fr:
                    floatrow_type = fr.attributes.setdefault("float_type", "figure")

                    if floatrow_type != "figure":
                        raise Exception(
                            "Mixed floatrows / subfloatrows aren't possible."
                        )

                    break

            lineheight = elem.attributes.get("lineheight", None)

            if use_input:
                graphic = f"\\input{{{url}}}"
            else:
                graphic = f"\\includegraphics{{{url}}}"

            if "scale" in elem.attributes:
                scale = elem.attributes["scale"]
                graphic = f"\\scalebox{{{scale}}}{{{graphic}}}"
            else:
                width = float(elem.attributes.get("width", "1"))

                width = f"{width}\\textwidth"

                if url.endswith(".pgf"):
                    graphic = f"\\resizebox{{{width}}}{{!}}{{{graphic}}}"
                elif url.endswith(".pdf_tex"):
                    graphic = f"\\def\\svgwidth{{{width}}}{{{graphic}}}"
                else:
                    graphic = f"\\includegraphics[width={width}]{{{url}}}"

            fontsize = elem.attributes.get("fontsize", "")
            svgbaselineskip = ""

            if fontsize:
                fontsize = fontsize.split(",")
                fontsize = [s.strip() for s in fontsize]

                if len(fontsize) == 1:
                    fontsize = fontsize[0]
                    size, unit = utils.string_to_float_unit(fontsize)

                    baselineskip = size * float((lineheight or "1.2"))
                    baselineskip = f"{baselineskip}{unit}"
                else:
                    fontsize, baselineskip = fontsize

                fontsize = f"\\fontsize{{{fontsize}}}{{{baselineskip}}}\\selectfont"
            elif lineheight:
                lineheight = float(lineheight)
                svgbaselineskip = f"""
                    \\setstretch{{{lineheight:.2f}}}"""

            placement = elem.attributes.get("placement", "t")

            head = (
                ""
                if any((float_row, sub_float_rows))
                else f"\\begin{{figure}}[{placement}]"
            )

            ffigboxoptions = attributes.get("ffigboxoptions")

            head += """
            \\ffigbox{}{{
            """.format(
                f"[{ffigboxoptions}]" if ffigboxoptions else ""
            )

            head += f"""
            {svgbaselineskip}{fontsize}
            """

            mid = """
            }{
            """

            tail = "" if any((sub_float_rows, float_row)) else "\\end{figure}"
            tail = (
                """}
            """
                + tail
            )

            head = pf.RawInline((head + graphic + mid), format="latex")

            caption = list(elem.content)
            if caption:
                caption = utils.make_caption(
                    elem.content,
                    elem.attributes.get("caption_title"),
                    subcaption=bool(sub_float_rows),
                )

            caption.append(pf.RawInline(f"\\label{{{figure_prefix}}}", format="latex"))

            tail = pf.RawInline(tail, format="latex")

            yield [head, *caption, tail]

        else:
            yield None


def get_elem_type(elem, elem_type):
    try:
        content = elem.content
    except AttributeError:
        return

    for e in content:
        if isinstance(e, elem_type):
            yield e
        else:
            for e_ in get_elem_type(e, elem_type):
                yield e_


"""
  \ttabbox
  {\caption{Reasons for exclusion}}
  {
     \begin{tabular}{lr} \toprule
     Reason for exclusion & N \\ \midrule
     age & 33 \\
     didn't receive therapy for aa & 1 \\
     insufficient data in medical records & 4 \\
     less than one episode with at least two valid photovisits & 16 \\
     no alopecia areata & 5 \\ \bottomrule
     \end{tabular}
  }
"""


def gather_inline(elem):
    if isinstance(elem, pf.Inline):
        yield elem
    else:
        if isinstance(elem, pf.ListContainer):
            content = iter(elem)
        else:
            content = iter(elem.content)

        for e in content:
            for e_ in gather_inline(e):
                yield e_


_CELL_OPTION_STRING = re.compile(r"^(?P<underline>_)?(?P<multicolumn>>+)?$")


def is_option_string(string_):
    return _CELL_OPTION_STRING.match(string_.strip())


def get_cell_options(cell):
    content = []
    underline = False
    multicolumn = 1

    for elem in cell.content:
        match = is_option_string(pf.stringify(elem))
        if match:
            groups = match.groupdict()
            multicolumn = groups.get("multicolumn", None)
            multicolumn = 1 if multicolumn is None else len(multicolumn) + 1
            underline = "underline" in groups
        else:
            content.append(elem)

    return content, underline, multicolumn


def format_row(elem, doc, is_header=False):
    cells = []
    lines = []

    first = True
    skip = 0

    for i, cell in enumerate(elem.content):
        if skip > 0:
            skip -= 1
            continue

        if not first:
            cells.append(pf.RawInline(" & ", format="latex"))
        else:
            first = False

        content, underline, multicolumn = get_cell_options(cell)
        from_, to = i + 1, i + multicolumn

        if underline:
            trim = "l" if from_ != 1 else ""
            trim += "r" if to != len(elem.content) else ""

            lines.append(
                pf.RawInline(f"\\cmidrule({trim}){{{from_}-{to}}}", format="latex")
            )

        if multicolumn > 1:
            skip = multicolumn - 1
            cells.append(
                pf.RawInline(f"\\multicolumn{{{multicolumn}}}{{c}}{{", format="latex")
            )
            cells.extend([c_ for c in content for c_ in gather_inline(c)])
            cells.append(pf.RawInline("}", format="latex"))
        else:
            cells.extend([c_ for c in content for c_ in gather_inline(c)])

    if cells:
        cells.append(pf.RawInline(" \\\\ \n", format="latex"))

        if not lines and is_header:
            lines.append(
                pf.RawInline(
                    "\\cmidrule{{{from_}-{to}}}".format(from_=1, to=len(elem.content)),
                    format="latex",
                )
            )

        cells.extend(lines)

    return cells


_ALIGNMEN_DICT = {
    "AlignLeft": "l",
    "AlignDefault": "l",
    "AlignRight": "r",
    "AlignCenter": "c",
}

TABLE_LINK = re.compile(r"\[\^((?P<label>[^\s\[\]]+),?)+\]_")

NUM_LABEL = re.compile(r"^\*(?P<number>[0-9]+)$")

_NUM_SYMBOLS = {
    "chicago": ["*", "†", "‡", "§", "‖", "\\#"],
    "lion": ["*", "†", "‡", "§", "◊", "\\#"],
    "bringhurst": ["*", "†", "‡", "§", "‖", "¶"],
    "wiley": ["*", "**", "†", "‡", "§", "‖", "¶"],
}

_SYMBOL_STYLE = "lion"


def _num_label_to_symbol(label):
    label = label.strip()

    match = NUM_LABEL.match(label)

    if not match:
        logger.debug("Didn't find a match in %s", label)
        return label

    number = int(match.group("number"))

    try:
        label = _NUM_SYMBOLS[_SYMBOL_STYLE][number - 1]
    except IndexError:
        label = str(number)

    return label


def _format_label(label):
    label = label.strip()

    if label.isalnum():
        return label

    label = "".join(
        le
        if le.isalnum()
        else "-".join(p.lower() for p in unicodedata.name(le).split())
        for le in label
    )

    return label


def table_links(elem, doc):
    table_note_prefix = doc.table_note_prefix

    if isinstance(elem, pf.Str):
        text = pf.stringify(elem)

        match = TABLE_LINK.search(text)
        if match:
            label = match.group("label")
            label = _num_label_to_symbol(label)
            label = _format_label(label)

            if doc.format == "latex":
                return pf.RawInline(
                    f"\\tnotex{{{table_note_prefix}:{label}}}", format="latex"
                )
            else:
                return pf.Link(pf.Str(label), url=label, classes=["table_note"])


def _has_header(elem):
    if elem.header is None:
        return

    if not any(e.content for e in elem.header.content):
        return

    # Apparently there is something in the header ...
    return True


def _get_env(attributes, environment=None):
    environment = environment or "tabular"

    alignment = attributes["alignment"]
    if environment == "tabular":
        head = f"""\\begin{{tabular}}{{{alignment}}}"""
        tail = """\\end{tabular}"""
    elif environment == "tabularx":
        width = float(attributes.get("width", "1"))
        head = f"""\\begin{{tabularx}}{{{width:.2f}\\textwidth}}{{{alignment}}}"""
        tail = """\\end{tabularx}"""

    return head, tail


def format_table(elem, doc):
    attributes = getattr(elem, "attributes", {})
    label = attributes.get("label")

    doc.table_name = table_name = label or ".".join(
        str(i) for i in utils.get_elem_count(doc, pf.Table, register="table")
    )
    doc.table_prefix = table_prefix = utils.make_label(doc, "tb:{}".format(table_name))
    doc.table_note_prefix = table_note_prefix = utils.make_label(
        doc, "tn:{}".format(table_name)
    )

    has_table_notes = False

    if isinstance(elem.next, pf.DefinitionList):
        has_table_notes = True
        table_notes_list = elem.next
        logger.debug("Table has notes")
    else:
        head = tail = ""

    elem = elem.walk(table_links)

    logger.debug(type(elem))

    cols = elem.cols
    attributes.setdefault(
        "alignment", "".join(_ALIGNMEN_DICT[a] for a in elem.alignment)
    )

    environment = attributes.get("environment")
    env_head, env_tail = _get_env(attributes, environment)

    head = env_head

    head += """\\toprule
    """
    tail = """ \\bottomrule
    """

    tail += env_tail

    logger.debug(elem)
    rows = []
    caption = []

    if elem.caption:
        caption_title = attributes.get("caption_title")

        caption = utils.make_caption(elem.caption, caption_title)

    caption.append(pf.RawInline(f"\\label{{{table_prefix}}}", format="latex"))

    if _has_header(elem):
        logger.debug("Got this header: %s", elem.header)
        row = format_row(elem.header, doc, is_header=True)

        if row is not None:
            rows.extend(row)

    for row in elem.content:
        row = format_row(row, doc)

        if row is not None:
            rows.extend(row)

    table_notes = []

    if has_table_notes:
        tablenotesoptions = attributes.get("tablenotesoptions")
        table_notes_head = """
        \\vspace{.5\\skip\\footins}
        """
        table_notes_head += """
        \\begin{{tablenotes}}{}""".format(
            f"[{tablenotesoptions}]" if tablenotesoptions else ""
        )

        table_notes_tail = """
        \\end{tablenotes}
        \\end{threeparttable}
        """

        for table_note in table_notes_list.content:
            term = "".join(pf.stringify(e) for e in table_note.term)
            term = _num_label_to_symbol(term)
            label = _format_label(term)

            definition = pf.Span(*gather_inline(table_note.definitions))
            logger.debug(definition)

            table_notes.extend(
                [
                    pf.RawInline(
                        f"""
                        \\item[{term}] \\label{{{table_note_prefix}:{label}}}""",
                        format="latex",
                    ),
                    definition,
                ]
            )

        if table_notes:
            head = (
                """\\begin{threeparttable}
            """
                + head
            )
            table_notes = [
                pf.RawInline(table_notes_head, format="latex"),
                *table_notes,
                pf.RawInline(table_notes_tail, format="latex"),
            ]

    if not rows:
        return None
    else:
        return (
            [
                pf.RawInline(head, format="latex"),
                *rows,
                pf.RawInline(tail, format="latex"),
            ],
            caption,
            table_notes,
        )


@utils.make_dependent(figure)
def render_sub_float_rows(elem, doc):
    attributes = getattr(elem, "attributes", {})

    if isinstance(elem, pf.Div) and "subfloatrows" in elem.classes:
        float_type = attributes.get("float_type", "figure")

        cols = attributes.get("cols")

        # Render the caption for the whole subfloatrow
        caption = attributes.get("caption", "")
        caption_title = attributes.get("caption_title")

        caption_content = []

        if caption:
            caption_content = utils.make_caption(caption, caption_title)

        # Render the content
        content = []

        mid = """
        }{
        """

        if float_type is None or float_type == "table":
            head = """\\begin{table}
            \\begin{subrow}
            """

            tail = """\\end{subrow}
            \\end{table}
            """
        elif float_type == "figure":
            placement = attributes.get("placement", "t")
            head = f"""\\begin{{figure}}[{placement}]
            \\ffigbox{{"""

            sub_head = """
            \\begin{subfloatrow}"""

            sub_tail = """\\end{subfloatrow}
            """
            tail = """
            }
            \\end{figure}"""

            if cols is not None:
                sub_head += f"[{cols}]"

            for e in get_elem_type(elem, pf.Para):
                content.append(e.content)

        utils.reverse_walk(elem, utils.rm_attributes("sub_float_rows"))

        if cols is not None:
            cols = int(cols)
            content = [
                [
                    pf.RawInline(sub_head, format="latex"),
                    *[c_ for c in content[i : i + cols] for c_ in c],
                    pf.RawInline(sub_tail, format="latex"),
                ]
                for i in range(0, len(content), cols)
            ]

        content = [c_ for c in content for c_ in c]

        return pf.Para(
            pf.RawInline(head, format="latex"),
            *content,
            pf.RawInline(mid, format="latex"),
            *caption_content,
            pf.RawInline(tail, format="latex"),
        )


@utils.make_dependent(render_sub_float_rows)
def render_float_rows(elem, doc):
    # If I don't check this here I will count the tables double, on the other
    # hand I need to keep track here otherwise I miss the sections and don't
    # count propertly

    if not isinstance(elem, pf.Table):
        utils.count_elements(
            elem,
            doc,
            pf.Table,
            register="table",
            scope={"relevant_elems": pf.Header, "level": 1},
        )

    attributes = getattr(elem, "attributes", {})

    if isinstance(elem, pf.Div) and "floatrow" in elem.classes:
        float_type = attributes.get("float_type", None)

        if float_type is None or float_type == "table":
            head = """\\begin{table}
            \\begin{floatrow}
            """
            tail = """\\end{floatrow}
            \\end{table}
            """

            content = []

            for e in get_elem_type(elem, pf.Table):
                utils.count_elements(
                    e,
                    doc,
                    pf.Table,
                    register="table",
                    scope={"relevant_elems": pf.Header, "level": 1},
                )

                table_, table_caption, table_notes = format_table(e, doc)

                if table_ is not None:
                    head_ = """\\ttabbox{
                        {"""

                    mid_ = """}
                    }{"""

                    tail_ = """
                    }"""
                    content.extend(
                        [
                            pf.RawInline(head_, format="latex"),
                            *table_,
                            *table_notes,
                            pf.RawInline(mid_, format="latex"),
                            *table_caption,
                            pf.RawInline(tail_, format="latex"),
                        ]
                    )

        elif float_type == "figure":
            placement = attributes.get("placement", "t")
            head = f"""\\begin{{figure}}[{placement}]
            \\begin{{floatrow}}"""
            tail = """\\end{floatrow}
            \\end{figure}"""
            content = []

            for e in get_elem_type(elem, pf.Para):
                content.extend(e.content)

        utils.reverse_walk(elem, utils.rm_attributes("float_row"))

        return pf.Para(
            pf.RawInline(head, format="latex"),
            *content,
            pf.RawInline(tail, format="latex"),
        )


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(figure),
        # finalize=_finalize.to_function(),
        # prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
