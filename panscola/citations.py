#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

# Third Party
import panflute as pf
import regex as re

# This Module
from panscola import process_headers, utils


class myCitation(pf.Citation):
    def __init__(self, *args, latex_command=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.latex_command = pf.utils.check_type(latex_command, list)


class myCite(pf.Cite):
    def __init__(self, *args, latex_command=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.latex_command = pf.utils.check_type(latex_command, list)


link_is_cite = re.compile(r"\[((?:(?:[^\^\s\[\]]+),?)+)\]")
str_is_cite = re.compile(r"(\[(?:(?:[^\^\s\[\]]+),?)+\]_)")
citation = re.compile(r"[^\s\[\],]+")


@utils.make_dependent(process_headers.process_headers)
def parse_citations(elem, doc):
    if isinstance(elem, pf.Link) and "table_note" not in elem.classes:
        text = pf.stringify(elem)

        if link_is_cite.search(text):
            return to_cite(text, doc)

    elif (
        hasattr(elem, "text")
        and len(elem.text) > 0
        and not isinstance(elem.parent, pf.Link)
        and not isinstance(elem, (pf.Code, pf.CodeBlock))
    ):

        text = elem.text

        if str_is_cite.search(text):
            content = []

            for s, c in utils.re_split(str_is_cite, text):
                content.append(s)

                if c:
                    content.append(to_cite(c, doc))

            return pf.Span(*content)


@utils.make_dependent()
def render_citations(elem, doc, string=False):
    if isinstance(elem, pf.Cite):
        if doc.format == "latex" and not doc.get_metadata(
            "doit_citeproc_for_latex", True
        ):

            latex_commands = []
            latex_command = "\\autocite{{{ids}}}"

            if hasattr(elem, "latex_command") and elem.latex_command:
                for command in elem.latex_command:
                    head = "" if command.startswith("\\") else "\\cite"
                    latex_command = "{head}{command}{{{{{{ids}}}}}}".format(
                        head=head, command=command
                    )

                    latex_commands.append(latex_command)
            else:
                latex_commands.append(latex_command)

            citations = ",".join([c.id for c in elem.citations])

            raw = "".join(lc.format(ids=citations) for lc in latex_commands)

            if string:
                return raw
            else:
                return pf.RawInline(raw, format="latex")
        else:
            if hasattr(elem, "latex_command") and "author" in elem.latex_command:

                names = []
                amount_citations = len(elem.citations)

                for i in range(1, amount_citations + 1):
                    citation = elem.citations[i - 1]
                    citation = doc.bibliography.get(citation.id, False)

                    if citation:
                        names_list = citation.get(
                            "author", citation.get("editor", False)
                        )

                        if names_list:
                            names.extend(utils.format_names(names_list))

                            if not i == amount_citations:
                                names.extend([pf.Str(", "), pf.Space])

                if names:
                    if elem.next:
                        if pf.stringify(names[-1]).endswith(".") and pf.stringify(
                            elem.next
                        ).startswith("."):
                            names[-1] = pf.Str(pf.stringify(names[-1])[:-1])

                            return pf.Span(*names)

            return pf.Cite(citations=elem.citations)


def to_cite(text, doc):
    text = text.strip("[]_")
    text = text.split(":")
    citations = []
    specifier = []

    if len(text) > 1:
        specifier = text.pop(0)
        specifier = specifier.split(",")

    kwargs = {}

    if specifier == "author":
        kwargs["mode"] = "AuthorInText"

    citations = [pf.Citation(c.group(0), **kwargs) for c in citation.finditer(text[0])]

    return myCite(citations=citations, latex_command=specifier)


@utils.make_dependent(process_headers._prepare)
def _prepare(doc):
    pass


@utils.make_dependent()
def _finalize(doc):
    pass


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(parse_citations, render_citations),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
