#!/usr/bin/env python
import string
import regex as re

import panflute as pf
import inflect

import utils
from utils import re_split

# For plurals
pluralize = inflect.engine()

is_abbreviation = re.compile(r'\+{1,2}´?(?:([^´\s_\+]+)´?)_')


def parse_abbreviations(elem, doc):
    if isinstance(elem, pf.Div) and 'abbr' in elem.classes:
        short = elem.attributes['short']
        identifier = elem.attributes.get('name', short.lower())
        long_ = pf.stringify(elem).strip()
        options = elem.attributes.get('options', '')

        doc.abbr['definitions'][identifier] = (short, long_, options)

        if identifier not in doc.abbr['latex_preamble']:
            doc.abbr['latex_preamble'][identifier] = pf.RawInline(
                (f'\\newabbreviation{options}'
                 f'{{{identifier}}}{{{short}}}{{{long_}}}\n'),
                format='latex'
            )

        return []

    elif hasattr(elem, 'text') and is_abbreviation.search(elem.text):
        content = []
        for s, c in re_split(is_abbreviation, elem.text):
            content.append(s)
            if c:
                pl = '1' if elem.text.startswith('++') else ''

                c = c.split("@")
                if len(c) > 1:
                    specifier = c.pop(0)
                else:
                    specifier = ''

                identifier = c.pop(0)
                uppercase = ('1'
                             if identifier[0] in string.ascii_uppercase
                             else '')

                # Now we know whether it's uppercase
                identifier = identifier.lower()
                doc.abbr['used'].append(identifier)

                attributes = {
                    'identifier': identifier,
                    'plural': pl,
                    'uppercase': uppercase,
                    'specifier': specifier,
                }

                content.append(pf.Link(
                    pf.Str(identifier),
                    classes=['abbr'],
                    attributes=attributes
                ))

        return pf.Span(*content)


def render_abbreviations(elem, doc):
    if isinstance(elem, pf.Link) and 'abbr' in elem.classes:
        identifier = elem.attributes['identifier']
        uppercase = elem.attributes['uppercase']
        plural = elem.attributes['plural']
        specifier = elem.attributes['specifier']

        if identifier not in doc.abbr['definitions']:
            return pf.Str(identifier)
        else:
            abbr = doc.abbr['definitions'][identifier]
            short = abbr[0]
            long_ = abbr[1]
            description = long_.title()  # needed later for definition liat
            options = abbr[2]

            if doc.format == 'latex':
                if identifier not in doc.abbr['rendered']:
                    options = f'[{options}]'
                    doc.abbr['rendered'].append(identifier)

                pl = 'pl' if plural else ''
                gls = 'Gls' if uppercase else 'gls'
                specifier = f'xtra{specifier}' if specifier else specifier

                raw = pf.RawInline(
                    f'\\{gls}{specifier}{pl}{{{identifier}}}',
                    format='latex'
                )

                return raw
            else:
                if uppercase:
                    short = short.upper()
                    long_ = long_.title()
                if plural:
                    short = pluralize.plural(short)
                    long_ = pluralize.plural(long_)

                if identifier not in doc.abbr['rendered']:
                    text = f'{long_} ({short})'
                    definition_item = pf.Span(
                        pf.Str(short),
                        identifier=f'abbr:{identifier}'
                    )

                    definition_description = pf.Para(pf.Str(description))
                    doc.abbr['appendix'].append((
                        identifier,
                        pf.DefinitionItem(
                            [definition_item],
                            [pf.Definition(definition_description)]
                        )
                    ))

                    doc.abbr['rendered'].append(identifier)
                else:
                    text = short

                return pf.Link(
                    pf.Str(text),
                    url=f'#abbr:{identifier}',
                    title=long_
                )


def _prepare(doc):
    doc.abbr = {
        'definitions': dict(),
        'used': list(),
        'rendered': list(),
        'appendix': list(),
        'latex_preamble': dict(),
    }


def _finalize(doc):
    appendix = doc.abbr['appendix']
    if appendix:
        heading = pf.Header(
            pf.Str('Abbreviations'),
            identifier='abbreviations',
            classes=['unnumbered']
        )
        doc.content.append(heading)
        appendix.sort(key=lambda x: x[0])
        appendix = map(lambda x: x[1], appendix)
        doc.content.append(pf.DefinitionList(*appendix))

    doc.metadata['preamble'] = pf.MetaInlines(
        *[value for key, value in doc.abbr['latex_preamble'].items()]
    )


prepare_dependency = utils.Dependent(_prepare)
finalize_dependency = utils.Dependent(_finalize)
parse_abbreviations_dependency = utils.Dependent(parse_abbreviations)
render_abbreviations_dependency = utils.Dependent(render_abbreviations)


def main(doc=None):
    order = utils.resolve_dependencies([
        parse_abbreviations_dependency,
        render_abbreviations_dependency,
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
