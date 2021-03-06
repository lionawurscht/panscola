#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

# Standard Library
import logging
import string

# Third Party
# 3rd party
import inflect
import panflute as pf
import regex as re
import slugify

# This Module
from panscola import utils

logger = logging.getLogger(__name__)


# For plurals
pluralize = inflect.engine()

is_abbreviation = re.compile(r"\+{1,2}´?(?:([^´\s_\+]+)´?)_")


@utils.make_dependent()
def parse_abbreviations_definitions(elem, doc):
    """
    Looks for divs with 'abbr' in their classes, then creates an
    abbreviation where the abbreviation is the div's attribute 'short'
    and the content of the div is the long version.

    :param elem:
    :param doc:
    """

    if isinstance(elem, pf.Div) and "abbr" in elem.classes:
        for attr in ["short", "long"]:
            if f"{attr}_{doc.format}" in elem.attributes:
                elem.attributes[attr] = elem.attributes.pop(f"{attr}_{doc.format}")

        short = elem.attributes.pop("short")

        identifier = elem.attributes.pop("name", slugify.slugify(short.lower()))

        aliases = set([identifier])
        aliases.update(
            [a.strip() for a in elem.attributes.pop("aliases", "").split(", ") if a]
        )

        description = elem.attributes.get("description", None)

        if description is not None and not description.strip().startswith("{"):
            elem.attributes["description"] = "{{{}}}".format(description)

        long_ = elem.attributes.pop("long", None) or pf.stringify(elem).strip()

        options = dict(**elem.attributes)
        latex_options = ",".join(f"{key}={value}" for key, value in options.items())

        if latex_options:
            latex_options = f"[{latex_options}]"

        if identifier in doc.abbr["definitions"]:
            old_short = doc.abbr["definitions"][identifier][0]
            logger.warning(
                f"Identifier {identifier!r} was already defined for "
                f"{old_short!r} and will now we overwritten with {short!r}"
            )

        doc.abbr["definitions"][identifier] = (short, long_, options)

        for alias in aliases:
            if alias in doc.abbr["aliases"]:
                old_identifier = doc.abbr["aliases"][alias]
                logger.warning(
                    f"Alias {alias!r} was already defined for "
                    f"{old_identifier!r} and will now we overwritten with "
                    f"{identifier!r}"
                )

            doc.abbr["aliases"][alias] = identifier

        doc.abbr["latex_preamble"][identifier] = pf.RawBlock(
            (
                f"\\newabbreviation{latex_options}"
                f"{{{identifier}}}{{{short}}}{{{long_}}}\n"
            ),
            format="latex",
        )

        return []


@utils.make_dependent(parse_abbreviations_definitions)
def parse_abbreviations(elem, doc):
    if hasattr(elem, "text") and is_abbreviation.search(elem.text):
        # text = pf.stringify(elem)
        text = elem.text
        content = []
        logger.debug(f"Original element: {elem}")

        for s, c in utils.re_split(is_abbreviation, text):
            logger.debug(f"re_plit of {text} gave {s} > {c}")
            content.append(s)

            if c:
                pl = "1" if elem.text.startswith("++") else ""

                c = c.split("@")

                if len(c) > 1:
                    specifier = c.pop(0)
                else:
                    specifier = ""

                identifier = c.pop(0)

                uppercase = "1" if identifier[0] in string.ascii_uppercase else ""

                # Now we know whether it's uppercase
                identifier = identifier.lower()

                if (
                    identifier not in doc.abbr["aliases"]
                    and identifier[-1] == "s"
                    and not pl
                    and identifier[:-1] in doc.abbr["aliases"]
                ):
                    identifier = identifier[:-1]
                    pl = "1"

                identifier = doc.abbr["aliases"].get(identifier, identifier)

                doc.abbr["used"].append(identifier)

                attributes = {
                    "identifier": identifier,
                    "plural": pl,
                    "uppercase": uppercase,
                    "specifier": specifier,
                }

                content.append(
                    pf.Link(pf.Str(identifier), classes=["abbr"], attributes=attributes)
                )

        return pf.Span(*content)


@utils.make_dependent()
def render_abbreviations(elem, doc):
    if isinstance(elem, pf.Link) and "abbr" in elem.classes:
        identifier = elem.attributes["identifier"]
        uppercase = elem.attributes["uppercase"]
        plural = elem.attributes["plural"]
        specifier = elem.attributes["specifier"]

        if identifier not in doc.abbr["definitions"]:
            return pf.Str(identifier)
        else:
            abbr = doc.abbr["definitions"][identifier]
            short = abbr[0]
            long_ = abbr[1]
            description = long_.title()  # needed later for definition liat
            options = abbr[2]

            if doc.format == "latex":
                if identifier not in doc.abbr["rendered"]:
                    doc.abbr["rendered"].append(identifier)

                pl = "pl" if plural else ""
                gls = "Gls" if uppercase else "gls"
                specifier = f"xtr{specifier}" if specifier else specifier

                raw = pf.RawInline(
                    f"\\{gls}{specifier}{pl}{{{identifier}}}", format="latex"
                )

                return raw
            else:

                category = options.get("category")

                if uppercase:
                    short = short.upper()
                    long_ = long_.title()

                if plural:
                    short = pluralize.plural(short)
                    long_ = pluralize.plural(long_)

                if identifier not in doc.abbr["rendered"]:
                    text = f"{long_} ({short})"

                    if category == "alwaysshort":
                        text = short
                    elif category == "nevershort":
                        text = long_

                    definition_item = pf.Span(
                        pf.Str(short), identifier=f"abbr:{identifier}"
                    )

                    definition_description = pf.Para(pf.Str(description))

                    if not options.get("type") == "ignored":
                        doc.abbr["appendix"].append(
                            (
                                identifier,
                                pf.DefinitionItem(
                                    [definition_item],
                                    [pf.Definition(definition_description)],
                                ),
                            )
                        )

                    doc.abbr["rendered"].append(identifier)
                else:
                    text = short

                    if category == "nevershort":
                        text = long_

                return pf.Link(pf.Str(text), url=f"#abbr:{identifier}", title=long_)


@utils.make_dependent()
def _prepare(doc):
    doc.abbr = {
        "definitions": dict(),
        "used": list(),
        "rendered": list(),
        "appendix": list(),
        "latex_preamble": dict(),
        "aliases": dict(),
    }


@utils.make_dependent()
def _finalize(doc):
    """_finalize

    :param doc:
    """

    swap_string = "\n".join(
        "  {short!r}: {identifier!r}\n  {long!r}: {identifier!r}".format(
            identifier="+{}_".format(identifier), short=short_, long=long_
        )
        for identifier, (short_, long_, __) in doc.abbr["definitions"].items()
    )
    logger.debug("Add abbreviations to vale substitutions:\n{}\n".format(swap_string))

    appendix = doc.abbr["appendix"]

    if appendix:
        heading = pf.Header(
            pf.Str("Abbreviations"), identifier="abbreviations", classes=["unnumbered"]
        )
        doc.content.append(heading)
        appendix.sort(key=lambda x: x[0])
        appendix = map(lambda x: x[1], appendix)
        doc.content.append(pf.DefinitionList(*appendix))

    if "preamble" in doc.metadata:
        existing_preamble = doc.metadata["preamble"].content
    else:
        existing_preamble = []

    doc.metadata["preamble"] = pf.MetaBlocks(
        *existing_preamble,
        *[value for key, value in doc.abbr["latex_preamble"].items()],
    )


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(parse_abbreviations, render_abbreviations),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
