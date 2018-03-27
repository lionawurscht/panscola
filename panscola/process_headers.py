#!/usr/bin/env python
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

import panflute as pf
import bibtexparser

from panscola import utils

false_strings = ('False', 'false')
true_strings = ('True', 'true')


def bibtexparser_customizations(record):
    record = bibtexparser.customization.author(record)
    record = bibtexparser.customization.editor(record)
    return record


@utils.make_dependent()
def process_headers(elem, doc):
    if isinstance(elem, pf.MetaMap):
        try:
            bib_file = pf.stringify(elem['bibliography'])
        except KeyError:
            bib_file = None

        if bib_file is not None:
            with open(bib_file) as bf:
                parser = bibtexparser.bparser.BibTexParser(
                    ignore_nonstandard_types=False,
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


@utils.make_dependent()
def _prepare(doc):
    doc.bibliography = False


@utils.make_dependent()
def _finalize(doc):
    pass


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(
            process_headers,
        ),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == '__main__':
    main()
