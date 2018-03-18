#!/usr/bin/env python
import panflute as pf
import bibtexparser

import utils

false_strings = ('False', 'false')
true_strings = ('True', 'true')


def bibtexparser_customizations(record):
    record = bibtexparser.customization.author(record)
    record = bibtexparser.customization.editor(record)
    return record


def process_headers(elem, doc):
    if isinstance(elem, pf.MetaMap):
        try:
            bib_file = pf.stringify(elem['bibliography'])
        except KeyError:
            bib_file = None

        if bib_file is not None:
            with open(bib_file) as bf:
                parser = bibtexparser.bparser.BibTexParser(
                    ignore_nonstandard_types=False
                )
                parser.customization = bibtexparser_customizations
                doc.bibliography = bibtexparser.load(
                    bf,
                    parser=parser,
                ).entries_dict

        for key, value in elem.content.items():
            string = pf.stringify(value).strip()

            if string in false_strings:
                elem[key] = pf.MetaBool(False)
            elif string in true_strings:
                elem[key] = pf.MetaBool(True)


def _prepare(doc):
    doc.bibliography = False


def _finalize(doc):
    pass


prepare_dependency = utils.Dependent(
    _prepare
)

finalize_dependency = utils.Dependent(_finalize)

process_headers_dependency = utils.Dependent(process_headers)


def main(doc=None):
    order = utils.resolve_dependencies([
        process_headers_dependency,
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
