#!/usr/bin/env python
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

import panflute as pf
import re

from panscola import utils

aligned = re.compile(r"^\\begin{aligned}|\\end{aligned}$")


class MyMath(pf.Math):
    __slots__ = ["identifier", "classes", "attributes"]

    def __init__(
        self,
        text,
        format="DisplayMath",
        identifier="",
        classes=[],
        attributes={},
    ):
        super().__init__(text, format)
        self._set_ica(identifier, classes, attributes)


@utils.make_dependent()
def custom_display_math(elem, doc):
    if isinstance(elem, pf.Math) and elem.format == "Displaymath":
        new_elem = MyMath(elem.text, elem.format)
        return new_elem


@utils.make_dependent()
def math(elem, doc):
    if (
        isinstance(elem, pf.Math)
        and elem.format == "DisplayMath"
        and doc.format == "latex"
    ):

        text = aligned.sub("", elem.text)
        if text.strip().startswith("\\begin"):
            return pf.RawInline(text, format="latex")
        else:
            return None


@utils.make_dependent()
def _prepare(doc):
    pass


@utils.make_dependent()
def _finalize(doc):
    pass


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(math),
        finalize=_finalize.to_function(),
        prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
