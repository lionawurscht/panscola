#!/usr/bin/env python
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))

import panflute as pf

from panscola import utils


@utils.make_dependent()
def figure(elem, doc):
    if isinstance(elem, pf.Image):
        url = getattr(elem, "url", "")
        use_input = any(url.endswith(s) for s in (".pgf", ".pdf_tex"))

        if doc.format == "latex":
            wrap = utils.string_to_bool(elem.attributes.get("wrap", ""), False)

            wrap_width = float(elem.attributes.get("wrap-width", "0.5"))

            if use_input:
                graphic = f"\\input{{{url}}}"
            else:
                graphic = f"\\includegraphics{{{url}}}"

            if "scale" in elem.attributes:
                scale = elem.attributes["scale"]
                graphic = f"\\scalebox{{{scale}}}{{{graphic}}}"
            else:
                if wrap:
                    width = wrap_width - 0.01
                else:
                    width = float(elem.attributes.get("width", "1"))

                width = f"{width}\\textwidth"

                if url.endswith(".pgf"):
                    graphic = f"\\resizebox{{{width}}}{{!}}{{{graphic}}}"
                elif url.endswith(".pdf_tex"):
                    graphic = f"\\def\\svgwidth{{{width}}}{{{graphic}}}"
                else:
                    graphic = f"\\includegraphics[width={width}]{{{url}}}"

            centering = elem.attributes.get("centering", "false")
            centering = utils.string_to_bool(centering, False)
            centering = "\\centering" if centering else ""

            fontsize = elem.attributes.get("fontsize", "")
            if fontsize:
                fontsize = fontsize.split(",")
                fontsize = [s.strip() for s in fontsize]
                if len(fontsize) == 1:
                    fontsize = fontsize[0]
                    size, unit = utils.string_to_float_unit(fontsize)

                    baselineskip = size * 1.2
                    baselineskip = f"{baselineskip}{unit}"
                else:
                    fontsize, baselineskip = fontsize

                fontsize = (
                    f"\\fontsize{{{fontsize}}}{{{baselineskip}}}\\selectfont"
                )

            if wrap:
                placement = elem.attributes.get("placement", "L")
                wrap_width = f"{wrap_width}\\textwidth"

                head = f"""\\begin{{wrapfigure}}{{{placement}}}{{{wrap_width}}}
                {centering}{fontsize}
                """
                tail = "\\end{wrapfigure}"

            else:
                placement = elem.attributes.get("placement", "t")
                head = f"""\\begin{{figure}}[{placement}]
                {centering}{fontsize}
                """
                tail = """\\end{figure}"""

            caption_head = "\\caption{%\n"
            caption = pf.Span(*elem.content)
            caption_tail = "\n}"

            head = pf.RawInline((head + graphic + caption_head), format="latex")
            tail = pf.RawInline((caption_tail + tail), format="latex")

            return [head, caption, tail]

        else:
            return None


def main(doc=None):
    pf.run_filters(
        utils.reduce_dependencies(figure),
        # finalize=_finalize.to_function(),
        # prepare=_prepare.to_function(),
        doc=doc,
    )


if __name__ == "__main__":
    main()
