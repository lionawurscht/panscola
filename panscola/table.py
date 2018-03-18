#!/usr/bin/env python
import panflute as pf
import re
import math

import pylatex as pl
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString

from utils import (check_type, count_elements, get_elem_count, panflute2output,
                   number_to_uppercase, create_nested_tags)
import utils
import latex_classes as lc

# ---------------------------
# Classes
# ---------------------------


class Table(pf.Table):
    def __init__(
        self,
        *args,
        col_cnt=None,
        row_cnt=None,
        total_width=0.8,
        **kwargs
    ):
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
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.col_span = check_type(col_span, int)
        self.row_span = check_type(row_span, int)
        self.covered = check_type(covered, bool)
        self.rm_horizontal_margins = check_type(rm_horizontal_margins, bool)


class TableRow(pf.TableRow):
    def __init__(self,
                 *args,
                 underlines=None,
                 top_space=False,
                 btm_space=False,
                 **kwargs):

        super().__init__(*args, **kwargs)

        self.underlines = ([]
                           if underlines is None
                           else pf.utils.check_type(underlines, list))
        self.top_space = check_type(top_space, bool)
        self.btm_space = check_type(btm_space, bool)


# ---------------------------
# Functions
# ---------------------------


def xml_code_to_table(elem, doc):
    if isinstance(elem, pf.CodeBlock) and 'panscola-table' in elem.classes:
        table_matrix = xml_to_table_matrix(elem.text)
        table_pf = table_matrix_to_pf(table_matrix, doc)
        table_pf = table_pf.walk(table_links)
        return table_pf


def xml_to_table_matrix(xml_input):
    table_soup = BeautifulSoup(xml_input, 'xml')

    if len(table_soup.table.find_all('caption')) > 1:
        raise ValueError('There should only be one caption.')
    caption = ''.join(str(c) for c in table_soup.caption.contents)

    if len(table_soup.find_all('table')) > 1:
        raise ValueError('There should only be one table.')

    rows = []
    for row in table_soup.table.find_all('row'):
        row_attributes = row.attrs
        row_attributes['underlines'] = [
            tuple(check_type(i, int) for i in u.strip().split('-'))
            for u in row_attributes.get('underlines', '').split(',') if u
        ]

        cells = []
        for cell in row.find_all('cell'):
            cell_attributes = cell.attrs
            cell_content = ''.join(str(c) for c in cell.contents)

            if cell_attributes:
                cells.append(((cell_content,), cell_attributes))
            else:
                cells.append(cell_content)

        rows.append([tuple(cells), row_attributes])

    if len(table_soup.table.find_all('footnotes')) > 1:
        raise ValueError('There should only be one footnote definition.')
    footnotes = ''.join(str(c) for c in table_soup.footnotes.contents)

    return([caption, rows, footnotes])


str_is_table_link = re.compile(r'\[\^((?:[^\s\[\]]+),?)+\]_')


def table_links(elem, doc):
    if isinstance(elem, pf.Str):
        text = pf.stringify(elem)
        if str_is_table_link.search(text):
            label = str_is_table_link.search(text).group(1)

            return pf.Link(pf.Str(label), url=label, classes=['table_note'])


def table_matrix_to_pf(matrix, doc):
    caption = matrix[0]
    table = matrix[1]
    footnotes = [i for i in list_to_elems([matrix[2]])]

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

                col_span = check_type(c_kwargs.get('col_span', 1), int)

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
                f'Expected {old_col_cnt} columns '
                f'but got {new_col_cnt} in {row}'
            )

        new_col_cnt = 0

        rows.append(TableRow(*cells, **r_kwargs))

    t_kwargs = {}
    if caption:
        t_kwargs['caption'] = [pf.Span(pf.Str(caption))]

    return pf.Div(
        Table(
            *rows,
            col_cnt=old_col_cnt,
            row_cnt=row_cnt, **t_kwargs
        ),
        *footnotes,
        classes=['custom_table'],
    )


def list_to_elems(list_):
    for i in list_:
        if isinstance(i, str):
            for e in pf.convert_text(i, 'rst'):
                yield e
        else:
            yield pf.Plain(pf.Str(str(i)))


def render_table(elem, doc):
    count_elements(
        elem,
        doc,
        pf.Table,
        register='table',
        scope=(None, pf.Header, 2),
    )

    if isinstance(elem, pf.Div) and 'custom_table' in elem.classes:

        if doc.format == 'latex':
            table = pf.RawBlock(render_table_latex(elem, doc), format='latex')
            return(table)

        elif doc.format == 'odt':
            return pf.RawBlock(
                render_table_odt(elem, doc),
                format='opendocument'
            )


def render_table_footer_latex(elem, doc, tex):
    if isinstance(elem, pf.DefinitionList):
        table_number = tuple(
            str(i) for i in get_elem_count(
                doc,
                pf.Table,
                register='table',
            )
        )

        with tex.create(lc.TableNotes(
            prefix='tn{}'.format('.'.join(table_number))
        )) as tn:

            tn.append(lc.Footnotesize())

            for definition_item in elem.content:
                term = ''.join(pf.stringify(e) for e in definition_item.term)

                definitions = [
                    panflute2output(d.content, format='latex')
                    for d in definition_item.definitions
                ]

                tn.add_item(term, ''.join(definitions))


def links_to_table_notes(elem, doc):
    if isinstance(elem, pf.Link) and 'table_note' in elem.classes:
        table_number = tuple(
            str(i) for i in get_elem_count(
                doc,
                pf.Table,
                register='table',
            )
        )

        return pf.RawInline(
            '\\tnotex{{tn{count}:{label}}}'.format(
                label=elem.url,
                count='.'.join(table_number)
            ),
            format='latex',
        )


def render_table_latex(elem, doc):
    tex = lc.ThreePartTable()
    table = elem.content[0]

    try:
        footer = elem.content[1]
        # this already adds the tablenotes environment
        render_table_footer_latex(footer.content[0], doc, tex)
    except IndexError:
        footer = None

    unoccupied_width = 1 - sum(table.width)
    unspecified_widths = len([w for w in table.width if not w])
    remaining_for_each = unoccupied_width / unspecified_widths

    widths = [w if w else remaining_for_each for w in table.width]

    # We want the table to occupy a maximum width
    widths = list(map(lambda x: x * table.total_width, widths))

    if hasattr(table, 'caption') and table.caption:
        caption = ''.join(pf.stringify(c) for c in table.caption)
        caption = (
            '\\caption{{{caption}}} \\\\ \\endfirsthead'
        ).format(caption=caption)

    table_spec = '@{{}} {columns} @{{}}'.format(
        columns=''.join(['p{{{}\\textwidth}}'.format(w) for w in widths]),
    )

    with tex.create(lc.myLongTable(table_spec, booktabs=True)) as lt:
        if hasattr(table, 'caption') and table.caption:
            lt.append(pl.Command(
                'caption',
                ''.join(pf.stringify(c) for c in table.caption),
            ))
            lt.append(pl.Command('tabularnewline'))
            lt.end_table_header()
        lt.append(pl.Command('bottomrule'))
        if footer is not None:
            lt.append(pl.Command('insertTableNotes'))
        lt.append(pl.Command('tabularnewline'))
        lt.end_table_last_footer()

        rows = []
        for r, row in enumerate(table.content):
            tex_row = []
            cells = []

            for c, cell in enumerate(row.content):
                cell = cell.walk(links_to_table_notes)
                cell_wrapper = lc.Span()
                content = panflute2output(cell.content, format='latex')

                cell_width = widths[c]
                if cell.col_span > 1:
                    cell_width = sum(widths[c:c+cell.col_span])

                minipage = pl.MiniPage(
                    width='{}\\columnwidth'.format(cell_width),
                    pos='t',
                    align='right',
                )
                minipage.append(pl.NoEscape(content))
                cell_wrapper.append(minipage)

                if cell.col_span > 1:
                    margins = '@{}' if cell.rm_horizontal_margins else ''
                    multicolumn = pl.MultiColumn(
                        cell.col_span,
                        align=pl.NoEscape(f'{margins}l{margins}'),
                        data=cell_wrapper,
                    )
                    tex_row.append(multicolumn)

                elif not cell.covered:
                    tex_row.append(cell_wrapper)

                if c == 0:
                    if row.top_space:
                        cell_wrapper.append(pl.Command('T'))
                    if row.btm_space:
                        cell_wrapper.append(pl.Command('B'))

            lt.add_row(tex_row, strict=False)

            if row.underlines:
                for underline in row.underlines:
                    start = underline[0]
                    stop = underline[1]
                    if start == 1 and stop == table.col_cnt:
                        lt.add_hline()
                    else:
                        if start > 1 and stop < table.col_cnt:
                            side = 'rl'
                        elif start > 1:
                            side = 'l'
                        else:
                            side = 'r'

                        lt.add_hline(
                            start=start,
                            end=stop,
                            cmidruleoption=side,
                        )

            rows.append(cells)

    return tex.dumps()


def render_table_odt(elem, doc):
    table = elem.content[0]
    table_number = tuple(
        str(i) for i in get_elem_count(
            doc,
            pf.Table,
            register='table',
        )
    )
    table_name = 'Table{}'.format(
        '_'.join(str(i) for i in table_number)
    )
    #
    table_root = BeautifulSoup('', 'xml')

    table_odt = Tag(name='table:table')

    caption_odt = Tag(name='text:p')
    caption_odt.attrs = {
        'text:style-name': 'Table'
    }

    caption_odt.contents.append(Tag(
        name='text:span',
        attrs={'text:style-name': 'Strong_20_Emphasis'},
    ))

    caption_odt.contents[0].contents.append(NavigableString('Table '))

    caption_number = Tag(name='text:sequence')
    caption_number.attrs = {
        'text:ref-name': f'ref{table_name}',
        'text:name': 'Table',
        'text:formula': 'ooow:Table+1',
        'style:num-format': '1'

    }
    caption_number.contents.append(NavigableString('.'.join(table_number)))
    caption_odt.contents[0].contents.append(caption_number)

    if hasattr(table, 'caption') and table.caption:
        caption_odt.contents[0].contents.append(NavigableString(': '))
        caption = ''.join(pf.stringify(c) for c in table.caption)
        caption_odt.contents.append(NavigableString(caption))

    table_root.contents.append(caption_odt)

    caption_number.contents.append(str(table_number))
    table_odt.attrs = {
        'table:name': table_name,
        'table:style-name': table_name,
        'table:template-name': 'Default Style',
    }
    table_root.contents.append(table_odt)
    try:
        footer = elem.content[1]
    except IndexError:
        footer = None

    unoccupied_width = 1 - sum(table.width)
    unspecified_widths = len([w for w in table.width if not w])
    remaining_for_each = unoccupied_width / unspecified_widths

    widths = [w if w else remaining_for_each for w in table.width]

    # We want the table to occupy a maximum width
    widths = map(lambda x: x * table.total_width, widths)

    styles = BeautifulSoup('', 'xml')

    column_style_names = []
    column_definitions = []
    for w, width in enumerate(widths):
        column_style_name = '{table_name}.{c}'.format(
            table_name=table_name,
            c=number_to_uppercase(w)
        )
        column_style_names.append(column_style_name)

        column_style = Tag(name='style:style')
        column_style.attrs = {
            'style:name': column_style_name,
            'style:family': 'table-column',
        }
        column_properties = Tag(name='style:table-column-properties')
        column_properties.attrs = {
                'style:rel-column-width': '{}*'.format(math.floor(width*1000))
        }
        column_style.contents.append(column_properties)

        styles.contents.append(column_style)

        column_definition = Tag(name='table:table-column')
        column_definition.attrs = {'table:style-name': column_style_name}

        column_definitions.append(column_definition)

    table_odt.contents.extend(column_definitions)

    for r, row in enumerate(table.content):
        row_odt = Tag(name='table:table-row')
        row_odt.attrs = {
            'table:style-name': '{table_name}.{r}'.format(
                table_name=table_name, r=r+1
            ),
        }

        row_cell_styles = []

        for c, cell in enumerate(row.content):

            if cell.covered:
                cell_odt = Tag(name='table:covered-table-cell')
                row_odt.contents.append(cell_odt)

                row_cell_styles.append(None)
            else:
                cell_odt = Tag(name='table:table-cell')

                cell_style_name = '{column_style}{r}'.format(
                    column_style=column_style_names[c],
                    r=r+1,
                )

                cell_style = Tag(name='style:style')
                cell_style.attrs = {
                    'style:name': cell_style_name,
                    'style:family': 'table-cell',
                    'style:writing-mode': 'page',
                }
                style_cell_properies = Tag(name='style:table-cell-properties')
                style_cell_properies.attrs = {
                        'fo:padding-left': '0.10cm',
                        'fo:padding-right': '0.10cm',
                        'fo:padding-top': '0.10cm',
                        'fo:padding-bottom': '0.10cm',
                }
                style_background_image = Tag(name='style:background-image')
                style_cell_properies.contents.append(style_background_image)
                cell_style.contents.append(style_cell_properies)

                row_cell_styles.append(cell_style)

                cell_odt.attrs = {
                    'table:style-name': cell_style_name,
                    'office:value-type': 'string',
                }

                if cell.col_span > 1:
                    cell_odt.attrs[
                        'table:number-columns-spanned'
                    ] = cell.col_span

                if cell.content:
                    cell_content = panflute2output(
                        cell.content,
                        format='opendocument'
                    ).strip()

                    cell_content = BeautifulSoup(
                        cell_content,
                        'lxml'
                    ).html.body

                    for t in cell_content.find_all('text:p'):
                        t.attrs['text:style-name'] = 'Table_20_contents'
                    cell_odt.contents = cell_content.contents
                else:
                    cell_content = Tag(name='text:p')
                    cell_content.attrs = {
                        'text:style-name': 'Table_20_contents',
                    }
                    cell_odt.contents.append(cell_content)

                row_odt.contents.append(cell_odt)

        if row.underlines:
            for underline in row.underlines:
                start = underline[0]
                stop = underline[1]
                for i in range(start - 1, stop):
                    cell_style = row_cell_styles[i]
                    if cell_style is None:
                        pass
                    else:
                        cell_style.contents[0].attrs[
                            'fo:border-bottom'
                        ] = '0.5pt solid #000000'

        add_top_space = table.content[r-1].btm_space if r else False

        if row.top_space or add_top_space:
            for cell_style in row_cell_styles:
                if cell_style is not None:
                    padding_top = cell_style.contents[0].attrs[
                        'fo:padding-top'
                    ]

                    padding_top = (float(padding_top.strip('cm'))
                                   + 0.05 * add_top_space
                                   + 0.05 * row.top_space)

                    cell_style.contents[0].attrs[
                        'fo:padding-top'
                    ] = f'{padding_top}cm'

        row_cell_styles = [cs for cs in row_cell_styles if cs is not None]
        styles.contents.extend(row_cell_styles)

        table_odt.contents.append(row_odt)

    styles = '\n'.join(c.prettify() for c in styles.contents)
    doc.auto_styles.append(styles)

    table = '\n'.join(str(c) for c in table_root.contents)
    print(table)
    return table


def _prepare(doc):
    custom_styles_root = BeautifulSoup('', 'xml')
    custom_styles_root.append(create_nested_tags(**{
        'name': 'style:style',
        'attrs': {
            'style:name': 'Keep_20_Caption_With_Next',
            'style:family': 'paragraph',
            'style:parent-style-name': 'Caption',
        },
        'contents': [
            {
                'name': 'style:paragraph-properties',
                'attrs': {'fo:keep-together': 'always'},
            },
        ],
    }))

    doc.auto_styles = []

    sequence_decls_root = BeautifulSoup('', 'xml')
    sequence_decls = Tag(name='text:sequence-decls')
    sequence_decls_root.contents.append(sequence_decls)
    for n in ['Illustration', 'Table', 'Text', 'Drawing']:
        t = Tag(name='text:sequence-decl')
        t.attrs = {
            'text:display-outline-level': str(
                doc.get_metadata('outline-level', '1')
            ),
            'text:name': n,
            'text:seperation-character': '.'
        }
        sequence_decls.contents.append(t)

    doc.sequence_decls = [
        '\n'.join(sd.prettify() for sd in sequence_decls_root.contents)
    ]


def _finalize(doc):
    doc.metadata['custom-automatic-styles'] = pf.MetaInlines(
        pf.RawInline('\n'.join(doc.auto_styles), format='opendocument')
    )


prepare_dependency = utils.Dependent(_prepare)
finalize_dependency = utils.Dependent(_finalize)
xml_code_to_table_dependency = utils.Dependent(xml_code_to_table)
render_table_dependency = utils.Dependent(render_table)


def main(doc=None):
    order = utils.resolve_dependencies([
        xml_code_to_table_dependency,
        render_table_dependency,
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
