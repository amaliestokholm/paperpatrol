#!/Users/georgiev/Installs/miniconda3/bin/python
"""
A quick and dirty parser for ArXiv
===================================

"""
import os
import sys
import time
import inspect
import traceback
import app
import institutes
from app import (
    ExportPDFLatexTemplate,
    DocumentSource,
    raise_or_warn,
    color_print,
    __DEBUG__,
)
from app import (
    get_coworker,
    filter_papers,
    ArXivPaper,
    highlight_papers,
    running_options,
    get_new_papers,
    shutil,
    get_catchup_papers,
    check_required_words,
    check_date,
    make_qrcode,
)


# __ROOT__ = '/'.join(os.path.abspath(inspect.getfile(inspect.currentframe())).split('/')[:-1])
__ROOT__ = os.path.abspath(".")

tpl = os.path.join(__ROOT__, "templates/daily.tpl")


class dailyTemplate(ExportPDFLatexTemplate):
    """Template used at MPIA
    which shows 3 figures and adapt the layout depending of figure aspect ratios
    """

    template = open(tpl, "r").read()

    compiler = "pdflatex "
    compiler_options = " -interaction=errorstopmode "

    def short_authors(self, document):
        """How to return short version of author list

        Parameters
        ----------
        document: app.Document instance
            latex document

        returns
        -------
        short_authors: string
            representation of the authors
        """
        print(document.short_authors)
        return document.short_authors

    def figure_to_latex(self, figure):
        """How to include the figures"""
        fig = ""
        for fname in figure.files:
            # as latex parses these lines first, one must prevent latex to find
            # dots in figure filenames apart from the extension
            if "." in fname:
                rootname, extension = os.path.splitext(fname)
                fname = "{%s}%s" % (rootname, extension)
            fig += r"    \includegraphics[width=\maxwidth, height=\maxheight,keepaspectratio]{"
            fig += fname + "}%\n"
        if len(figure.files) > 1:
            fig = fig.replace(
                r"\maxwidth",
                "{0:0.1f}".format(0.9 * 1.0 / len(figure.files)) + r"\maxwidth",
            )
        caption = (
            r"""    \caption{Fig. """
            + str(figure._number)
            + """: """
            + str(figure.caption)
            + r"""}"""
        )
        return fig, caption

    def apply_to_document(self, document):
        """Fill the template

        Parameters
        ----------
        document: app.Document instance
            latex document

        Returns
        -------
        txt: string
            latex source of the final document
        """
        txt = self.template.replace("<MACROS>", document._macros)
        if document._identifier is not None:
            txt = txt.replace(
                "<IDENTIFIER>",
                r"\hl{{{0:s}}}".format(document._identifier) or "Abstract ",
            )
        else:
            txt = txt.replace("<IDENTIFIER>", "Abstract ")
        txt = txt.replace("<TITLE>", document.title)
        txt = txt.replace("<AUTHORS>", self.short_authors(document))
        txt = txt.replace("<ABSTRACT>", document.abstract.replace(r"\n", " "))

        for where, figure in zip(
            "ONE TWO THREE".split(), self.select_figures(document, N=3)
        ):
            fig, caption = self.figure_to_latex(figure)
            if where == "ONE":
                special = fig.replace(
                    r"[width=\maxwidth, height=\maxheight,keepaspectratio]", ""
                )
                txt = txt.replace("<FILE_FIGURE_ONE>", special)
            fig = fig.replace(r"\\", "")
            txt = txt.replace("<FIGURE_{0:s}>".format(where), fig)
            txt = txt.replace("<CAPTION_{0:s}>".format(where), caption)
        if "<CAPTION_TWO>" in txt:
            txt = txt.replace("<FIGURE_TWO>", "")
            txt = txt.replace("<CAPTION_TWO>", "")
        if "<CAPTION_THREE>" in txt:
            txt = txt.replace("<FIGURE_THREE>", "")
            txt = txt.replace("<CAPTION_THREE>", "")

        txt = txt.replace("<COMMENTS>", document.comment or "")
        txt = txt.replace("<DATE>", document.date)

        return txt


def main(workplaceidstr, template=None, options=None):
    if options is None:
        options = app.running_options()
    identifier = options.get("identifier", None)
    paper_request_test = identifier not in (None, "None", "", "none")
    hl_authors = options.get("hl_authors", None)
    hl_request_test = hl_authors not in (None, "None", "", "none")
    sourcedir = options.get("sourcedir", None)
    catchup_since = options.get("since", None)
    select_main = options.get("select_main", False)

    __DEBUG__ = options.get("debug", False)

    workplace = institutes.Institute(workplaceidstr)
    institute_words = workplace.institute_words

    if __DEBUG__:
        print("Debug mode on")

    if not hl_request_test:
        coworker_list = options.get("coworker", os.path.join(workplace.institutedir, "coworker.txt"))
        coworker = get_coworker(coworker_list)
    else:
        coworker = [author.strip() for author in hl_authors.split(",")]

    if sourcedir not in (None, ""):
        document_source = DocumentSource(sourcedir, autoselect=(not select_main))
        document_source.identifier = sourcedir
        keep, matched_authors = highlight_papers([document_source], coworker)
        document_source.compile(template=template)
        name = document_source.outputname.replace(".tex", ".pdf").split("/")[-1]
        shutil.move(sourcedir + "/" + name, document_source.identifier + ".pdf")
        print("PDF postage:", document_source.identifier + ".pdf")
        return
    elif identifier in (None, "", "None"):
        if catchup_since not in (None, "", "None", "today"):
            papers = get_catchup_papers(since=catchup_since, skip_replacements=True)
        else:
            papers = get_new_papers(
                skip_replacements=True, appearedon=check_date(options.get("date"))
            )
        keep, matched_authors = filter_papers(papers, coworker)
    else:
        papers = [
            ArXivPaper(
                identifier=identifier.split(":")[-1],
                appearedon=check_date(options.get("date")),
            )
        ]
        keep, matched_authors = highlight_papers(papers, coworker)

    # make sure no duplicated papers
    keep = list({k.identifier: k for k in keep}.values())

    issues = []
    non_issues = []

    for paper in keep:
        try:
            paper.get_abstract()
            s = paper.retrieve_document_source(__ROOT__ + "/tmp/")
            _identifier = paper.identifier.split(":")[-1]
            if s is not None:
                institute_test = check_required_words(s, institute_words)

                # Filtering out bad matches
                if (not institute_test) and (not paper_request_test):
                    raise RuntimeError(
                        "Not an institute paper -- "
                        + check_required_words(s, institute_words, verbose=True)
                    )
            else:
                print('This paper is PDF only, we assume it belongs to the group')
                paper_request_test = True
                # Make s for pdfonly


            if paper_request_test or institute_test:
                make_qrcode(_identifier)
                s.compile(template=template)
                name = s.outputname.replace(".tex", ".pdf").split("/")[-1]
                destination = os.path.join(__ROOT__, 'done_toprint', _identifier + ".pdf")
                time.sleep(2)
                shutil.move(__ROOT__ + "/tmp/" + name, destination)
                print("PDF postage:", _identifier + ".pdf")
            else:
                print("Not from group... Skip.")
            non_issues.append((paper.identifier, ", ".join(paper.highlight_authors)))
        except Exception as error:
            issues.append(
                (paper.identifier, ", ".join(paper.highlight_authors), str(error))
            )
            raise_or_warn(error, debug=__DEBUG__)

    print(""" Issues =============================== """)
    for issue in issues:
        color_print("[{0:s}] {1:s} \n {2:s}".format(*issue), "red")

    print(""" Matched Authors ====================== """)
    for name, author, pid in matched_authors:
        color_print("[{0:s}] {1:10s} {2:s}".format(pid, name, author), "green")

    print(""" Compiled outputs ===================== """)
    for issue in non_issues:
        color_print("[{0:s}] {1:s}".format(*issue), "cyan")

    return non_issues


if __name__ == "__main__":
    main(institute='bham', template=dailyTemplate())
