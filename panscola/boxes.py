#!/usr/bin/env python
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

import panflute as pf
from bs4 import BeautifulSoup

from panscola import utils


@utils.make_dependent()
def boxes(elem, doc):
    if isinstance(elem, pf.Str) and elem.text.startswith('::box-'):
        box_count = int(elem.text.split('::box-')[1])
        if doc.format == 'latex':
            return pf.RawInline(f'\\boxes{{{box_count}}}', format='latex')
        if doc.format == 'odt':
            box_root = BeautifulSoup('', 'xml')
            box_root.append(utils.create_nested_tags(**{
                'name': 'draw:custom-shape',
                'attrs': {
                    'text:anchor-type': 'as-char',
                    'svg:y': '-0.1799in',
                    'draw:z-index': '0',
                    'draw:name': 'Shape1',
                    'draw:style-name': 'gr1',
                    'draw:text-style-name': 'P6',
                    'svg:width': '0.1406in',
                    'svg:height': '0.2004in',
                },
                'contents': [
                    {'name': 'text:p'},
                    {
                        'name': 'draw:enhanced-geometry',
                        'attrs': {
                            'svg:viewBox': '0 0 21600 21600',
                            'draw:type': 'rectangle',
                            'draw:enhanced-path': ('M 0 0 L 21600 0 21600 '
                                                   '21600 0 21600 0 0 Z N'),
                        }
                    }
                ]
            }))

            return pf.RawInline(
                utils.soup_to_string(box_root),
                format='opendocument',
            )


@utils.make_dependent()
def _prepare(doc):
    doc.auto_styles = getattr(doc, 'auto_styles', [])

    custom_styles_root = BeautifulSoup('', 'xml')

    custom_styles_root.append(utils.create_nested_tags(**{
        'name': 'style:style',
        'attrs': {
            'style:name': 'gr1',
            'style:family': 'graphic',
        },
        'contents': [
            {
                'name': 'style:graphic-properties',
                'attrs': {
                    'svg:stroke-color': '#000000',
                    'draw:fill': 'none',
                    'draw:textarea-horizontal-align': 'justify',
                    'draw:textarea-vertical-align': 'middle',
                    'draw:auto-grow-height': 'false',
                    'fo:min-height': '0.2in',
                    'fo:min-width': '0.1402in',
                    'style:run-through': 'foreground',
                    'style:wrap': 'run-through',
                    'style:number-wrapped-paragraphs': 'no-limit',
                    'style:vertical-pos': 'from-top',
                    'style:horizontol-pos': 'from-left',
                    'style:horizontal-rel': 'paragraph',
                },
            },
        ],
    }))

    doc.auto_styles.extend([utils.soup_to_string(custom_styles_root, '\n')])

    doc.metadata['custom-automatic-styles'] = pf.MetaInlines(
        pf.RawInline('\n'.join(doc.auto_styles), format='opendocument')
    )


@utils.make_dependent()
def _finalize(doc):
    doc.metadata['custom-automatic-styles'] = pf.MetaInlines(
        pf.RawInline('\n'.join(doc.auto_styles), format='opendocument')
    )


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(
            boxes,
        ),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == '__main__':
    main()
