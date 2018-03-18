#!/usr/bin/env python
import panflute as pf


def prepare(doc):
    doc.abbreviations = []
    doc.bibliography = []


def fix_appendix(elem, doc):
    if (
        isinstance(elem, pf.Header)
        and pf.stringify(elem) in ('Bibliography', 'Abbreviations')
    ):
        list_ = (doc.abbreviations
                 if pf.stringify(elem) == 'Abbreviations'
                 else doc.bibliography)

        elem.classes.append('page-break-before')

        list_.append(elem)
        next_ = elem.next
        while True:
            next = next_
            if (
                (isinstance(next, pf.Header) and next.level == elem.level)
                or next is None
            ):
                break
            else:
                next_ = next.next
                list_.append(next)
                next.parent.content.pop(next.index)
                return []


html_formats = ('html', 'html5')


def render_page_break_before(elem, doc):
    if hasattr(elem, 'classes') and 'page-break-before' in elem.classes:
        elem.classes.remove('page-break-before')
        index = elem.index

        if isinstance(elem, pf.Block):
            raw_builder = pf.RawBlock
        elif isinstance(elem, pf.Inline):
            raw_builder = pf.RawInline

        raw = None
        if doc.format == 'latex':
            raw = raw_builder('\\clearpage', format='latex')
        elif doc.format == 'odt':
            raw = raw_builder(
                '<text:p text:style-name="Break_20_Before" />',
                format='opendocument'
            )

        if raw is not None:
            elem.parent.content.insert(index + 1, raw)
            elem.parent.content.insert(index + 2, elem)
            return []


def finalize(doc):
    doc.content.extend(doc.bibliography)
    doc.content.extend(doc.abbreviations)

    doc.walk(render_page_break_before)


def main(doc=None):
    pf.run_filters([fix_appendix], prepare=prepare, finalize=finalize, doc=doc)


if __name__ == '__main__':
    main()
