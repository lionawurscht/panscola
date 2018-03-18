#!/usr/bin/env python
import regex as re

import panflute as pf

import process_headers
import utils
from utils import re_split, format_names


class myCitation(pf.Citation):
    def __init__(self, *args, latex_command=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.latex_command = pf.utils.check_type(latex_command, list)


class myCite(pf.Cite):
    def __init__(self, *args, latex_command=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.latex_command = pf.utils.check_type(latex_command, list)


link_is_cite = re.compile(r'\[((?:(?:[^\s\[\]]+),?)+)\]')
str_is_cite = re.compile(r'(\[(?:(?:[^\s\[\]]+),?)+\]_)')
citation = re.compile(r'[^\s\[\],]+')


def parse_citations(elem, doc):
    if isinstance(elem, pf.Link) and 'table_note' not in elem.classes:
        text = pf.stringify(elem)
        if link_is_cite.search(text):
            return to_cite(text, doc)

    elif (hasattr(elem, 'text')
          and len(elem.text) > 0
          and not isinstance(elem.parent, pf.Link)
          and not isinstance(elem, (pf.Code, pf.CodeBlock))):

        text = elem.text
        if str_is_cite.search(text):
            content = []
            for s, c in re_split(str_is_cite, text):
                content.append(s)
                if c:
                    content.append(to_cite(c, doc))

            return pf.Span(*content)


def render_citations(elem, doc, string=False):
    if isinstance(elem, pf.Cite):
        if (
            doc.format == 'latex'
            and not doc.get_metadata('doit_citeproc_for_latex', True)
        ):

            latex_commands = []
            latex_command = '\\autocite{{{ids}}}'
            if hasattr(elem, 'latex_command') and elem.latex_command:
                for command in elem.latex_command:
                    head = '' if command.startswith('\\') else '\\cite'
                    latex_command = '{head}{command}{{{{{{ids}}}}}}'.format(
                        head=head,
                        command=command
                    )

                    latex_commands.append(latex_command)
            else:
                latex_commands.append(latex_command)

            citations = ','.join([c.id for c in elem.citations])

            raw = ''.join(lc.format(ids=citations) for lc in latex_commands)

            if string:
                return raw
            else:
                return pf.RawInline(raw, format='latex')
        else:
            if (
                hasattr(elem, 'latex_command')
                and 'author' in elem.latex_command
            ):

                names = []
                amount_citations = len(elem.citations)
                for i in range(1, amount_citations + 1):
                    citation = elem.citations[i - 1]
                    citation = doc.bibliography.get(citation.id, False)
                    if citation:
                        names_list = citation.get(
                            'author',
                            citation.get('editor', False)
                        )

                        if names_list:
                            names.extend(format_names(names_list))
                            if not i == amount_citations:
                                names.extend([pf.Str(', '), pf.Space])

                if names:
                    if elem.next:
                        if (
                            pf.stringify(names[-1]).endswith('.')
                            and pf.stringify(elem.next).startswith('.')
                        ):
                            names[-1] = pf.Str(pf.stringify(names[-1])[:-1])
                            return(pf.Span(*names))

            return pf.Cite(citations=elem.citations)


def to_cite(text, doc):
    text = text.strip("[]_")
    text = text.split(":")
    citations = []
    specifier = []

    if len(text) > 1:
        specifier = text.pop(0)
        specifier = specifier.split(',')

    kwargs = {}
    if specifier == 'author':
        kwargs['mode'] = 'AuthorInText'

    citations = [
        pf.Citation(c.group(0), **kwargs) for c in citation.finditer(text[0])
    ]

    return myCite(citations=citations, latex_command=specifier)


def _prepare(doc):
    pass


def _finalize(doc):
    pass


prepare_dependency = utils.Dependent(
    _prepare,
    [process_headers.prepare_dependency]
)

finalize_dependency = utils.Dependent(_finalize)

parse_citations_dependecy = utils.Dependent(
    parse_citations,
    [process_headers.process_headers_dependency]
)

render_citations_dependency = utils.Dependent(render_citations)


def main(doc=None):
    order = utils.resolve_dependencies([
        parse_citations_dependecy,
        render_citations_dependency
    ])
    filters = [d.object_ for d in order]

    pf.run_filters(
        filters,
        finalize=utils.function_fron_dependencies([finalize_dependency]),
        prepare=utils.function_fron_dependencies([prepare_dependency]),
        doc=doc
    )


if __name__ == '__main__':
    main()
