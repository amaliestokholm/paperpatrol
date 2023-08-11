"""
A quick and dirty parser for ArXiv
===================================
"""
import os
import sys
import time
import inspect
from typing import TypedDict

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
from app import (
    ExportCompileTemplate,
    compile_template_with_aux_from_source,
    compile_template_without_source,
)


# __ROOT__ = '/'.join(os.path.abspath(inspect.getfile(inspect.currentframe())).split('/')[:-1])
__ROOT__ = os.path.abspath(".")
outputdir = os.path.join(__ROOT__, "toprint")
if not os.path.exists(outputdir):
    print(f"Creates outputdir: {outputdir}")
    os.mkdir(outputdir)

with open(os.path.join(__ROOT__, "templates/daily.tpl"), "r") as fp:
    tpl = fp.read()


def apply_pdfonly_template_to_document(paper: ArXivPaper) -> str:
    if paper.appearedon in (None, "", "None"):
        date = paper.date or ""
    else:
        date = "Appeared on " + paper.appearedon

    # not sure if ArXivPaper always has abstract+authors at this point...
    abstract = paper.abstract
    authors = paper.short_authors

    return apply_replacements(
        tpl,
        {
            "macros": "",
            "identifier": paper.identifier,
            "title": paper.title,
            "authors": authors,
            "abstract": abstract,
            "file_figure_one": "PDFONLY",
            "figure_one": "",
            "caption_one": "",
            "figure_two": "",
            "caption_two": "",
            "figure_three": "",
            "caption_three": "",
            "comments": paper.comment.replace("\\ ", " "),
            "date": date,
        },
    )


class Replacements(TypedDict):
    macros: str
    identifier: str
    title: str
    authors: str
    abstract: str
    file_figure_one: str
    figure_one: str
    caption_one: str
    figure_two: str
    caption_two: str
    figure_three: str
    caption_three: str
    comments: str
    date: str


class dailyTemplate(ExportPDFLatexTemplate):
    """Template used at MPIA
    which shows 3 figures and adapt the layout depending of figure aspect ratios
    """

    compiler_options = " -interaction=errorstopmode "
    template = tpl

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

    def figure_to_latex(self, figure) -> tuple[str, str]:
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
        return apply_replacements(self.template, self.get_replacements(document))

    def get_replacements(self, document) -> Replacements:
        macros = document._macros
        title = document.title
        authors = self.short_authors(document)
        abstract = document.abstract.replace(r"\n", " ")
        comments = document.comment or ""
        date = document.date
        if document._identifier is not None:
            identifier = r"\hl{{{0:s}}}".format(document._identifier) or "Abstract "
        else:
            identifier = "Abstract "

        figures = [self.figure_to_latex(f) for f in self.select_figures(document, N=3)]
        if len(figures) >= 1:
            f1, c1 = figures[0]
            f1 = f1.replace(r"\\", "")
        else:
            f1, c1 = "", ""
        if len(figures) >= 2:
            f2, c2 = figures[1]
            f2 = f2.replace(r"\\", "")
        else:
            f2, c2 = "", ""
        if len(figures) >= 3:
            f3, c3 = figures[2]
            f3 = f3.replace(r"\\", "")
        else:
            f3, c3 = "", ""

        file_figure_one = f1.replace(
            r"[width=\maxwidth, height=\maxheight,keepaspectratio]", ""
        )

        return {
            "macros": macros,
            "identifier": identifier,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "file_figure_one": file_figure_one,
            "figure_one": f1,
            "caption_one": c1,
            "figure_two": f2,
            "caption_two": c2,
            "figure_three": f3,
            "caption_three": c3,
            "comments": comments,
            "date": date,
        }


def apply_replacements(template: str, replacements: Replacements) -> str:
    txt = template
    for search, replace in replacements.items():
        txt = txt.replace("<%s>" % search.upper(), replace)
    return txt


def main(workplaceidstr, template: ExportCompileTemplate | None = None, options=None):
    if template is None:
        template = ExportPDFLatexTemplate()
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
        coworker_list = options.get(
            "coworker", os.path.join(workplace.institutedir, "coworker.txt")
        )
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
            directory = __ROOT__ + "/tmp/"
            s = paper.retrieve_document_source(directory)
            _identifier = paper.identifier.split(":")[-1]
            if s is not None:
                institute_test = check_required_words(s, institute_words)

                # Filtering out bad matches
                if (not institute_test) and (not paper_request_test):
                    raise RuntimeError(
                        "Not an institute paper -- "
                        + check_required_words(s, institute_words, verbose=True)
                    )

                if paper_request_test or institute_test:
                    make_qrcode(_identifier)
                    outputname = s.outputname
                    compile_template_with_aux_from_source(
                        compiler=template.compiler,
                        compiler_options=template.compiler_options,
                        directory=directory,
                        fname=s.fname,
                        outputname=outputname,
                        data=template.apply_to_document(s),
                    )
                    name = outputname.replace(".tex", ".pdf").split("/")[-1]
                    destination = os.path.join(
                        __ROOT__, outputdir, _identifier + ".pdf"
                    )
                    time.sleep(2)
                    shutil.move(__ROOT__ + "/tmp/" + name, destination)
                    print("PDF postage:", _identifier + ".pdf")
                else:
                    print("Not from group... Skip.")
                non_issues.append(
                    (paper.identifier, ", ".join(paper.highlight_authors))
                )
            else:
                # python3 dailyarxiv.py --identifier 2308.02253
                print("This paper is PDF only, we assume it belongs to the group")
                institute_test = True

                if paper_request_test or institute_test:
                    make_qrcode(_identifier)
                    outputname = os.path.join(directory, "arxiver.tex")
                    compile_template_without_source(
                        compiler=template.compiler,
                        compiler_options=template.compiler_options,
                        directory=directory,
                        outputname=outputname,
                        data=apply_pdfonly_template_to_document(paper),
                    )
                    name = outputname.replace(".tex", ".pdf").split("/")[-1]
                    destination = os.path.join(
                        __ROOT__, outputdir, _identifier + ".pdf"
                    )
                    time.sleep(2)
                    shutil.move(__ROOT__ + "/tmp/" + name, destination)
                    print("PDF postage:", _identifier + ".pdf")
                else:
                    print("Not from group... Skip.")
                non_issues.append(
                    (paper.identifier, ", ".join(paper.highlight_authors))
                )
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
    main(workplaceidstr="bham", template=dailyTemplate())
