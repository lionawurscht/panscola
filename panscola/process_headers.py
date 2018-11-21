#!/usr/bin/env python
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

import logging

logger = logging.getLogger(__name__)

import panflute as pf
import bibtexparser

logging.getLogger("bibtexparser.bparser").setLevel(logging.WARNING)

from panscola import utils


def bibtexparser_customizations(record):
    record = bibtexparser.customization.author(record)
    record = bibtexparser.customization.editor(record)
    return record


@utils.make_dependent()
def process_headers(elem, doc):
    pass


@utils.make_dependent()
def _prepare(doc):
    debug = doc.get_metadata("doit_debug", None, builtin=False)
    if debug is None:
        logging.basicConfig(level=logging.INFO)
    else:
        if isinstance(debug, pf.MetaBool):
            debug = debug.boolean
        else:
            debug = pf.stringify(debug)
            debug = utils.string_to_bool(debug.strip())

        debug = bool(debug)

        logging_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(level=logging_level)

    doc.bibliography = False
    metadata = doc.metadata

    try:
        bib_file = pf.stringify(metadata["bibliography"])
    except KeyError:
        bib_file = None

    if bib_file is not None:
        with open(bib_file) as bf:
            parser = bibtexparser.bparser.BibTexParser(
                ignore_nonstandard_types=False
            )
            parser.customization = bibtexparser_customizations
            doc.bibliography = bibtexparser.load(bf, parser=parser).entries_dict

    for key, value in metadata.content.items():
        string = pf.stringify(value).strip()

        t_f = utils.string_to_bool(string, None)
        if t_f is not None:
            metadata[key] = pf.MetaBool(t_f)


@utils.make_dependent()
def _finalize(doc):
    pass


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(process_headers),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
