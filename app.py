"""
A quick and dirty parser for ArXiv
===================================

"""

import datetime
import os
import re
import sys
from typing import Protocol
import xml.etree.ElementTree as ET

# from __future__ import (absolute_import, division, print_function)
import traceback
import operator
from glob import glob
import subprocess

from html.parser import HTMLParser
from urllib.request import urlopen
import tarfile
import shutil
import locale
import codecs

import inspect
import qrcode

# directories
__ROOT__ = os.path.abspath( ".")  ## '/'.join(os.path.abspath(inspect.getfile(inspect.currentframe())).split('/')[:-1])
tmpdir = os.path.join(__ROOT__, 'tmp')
__DEBUG__ = False

iteritems = operator.methodcaller("items")
itervalues = operator.methodcaller("values")
basestring = (str, bytes)
"""
PY3 = sys.version_info[0] > 2

if PY3:
    iteritems = operator.methodcaller('items')
    itervalues = operator.methodcaller('values')
    basestring = (str, bytes)
else:
    range = xrange
    from itertools import izip as zip
    iteritems = operator.methodcaller('iteritems')
    itervalues = operator.methodcaller('itervalues')
    basestring = (str, unicode)
"""


def make_qrcode(identifier):
    qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(f"https://arxiv.org/abs/{str(identifier)}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qrfig = os.path.join(tmpdir, "qrcode.png")
    with open(qrfig, "wb") as f:
        img.save(f)



def raise_or_warn(exception, limit=5, file=sys.stdout, debug=False):
    """Raise of warn for exceptions. This helps debugging"""
    if (__DEBUG__) or (debug):
        raise exception
    else:
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # print(exception, '\n')
        traceback.print_exception(exception)


def balanced_braces(args, limit=None, strict=False):
    """Find tokens between {}

    Parameters
    ----------
    args: list or str
        data to parse

    Returns
    -------
    parts: seq
        extracted parts
    """
    parts = []
    if isinstance(args, list):
        for x in args:
            parts += balanced_braces(x)
        return parts[:limit]
    if isinstance(args, bytes):
        raise TypeError("str is required, not bytes")
    assert isinstance(args, str)
    it = re.finditer(r"[{}]|\\.|%.*", args)
    parts = []
    num = 0
    current_start = None
    for mo in it:
        s = mo.group(0)
        if s[0] == "%":
            # Comment - skip
            continue
        if s == "{":
            if num == 0:
                # Start argument
                assert current_start is None
                current_start = mo.end()
            num += 1
            continue
        if s == "}":
            if num == 0:
                if strict:
                    raise Exception(
                        "parse error: unmatched '}' at position %s" % mo.start()
                    )
                continue
            num -= 1
            if num == 0:
                # End argument
                assert current_start is not None
                parts.append(args[current_start : mo.start()])
                if limit is not None and len(parts) >= limit:
                    return parts[:limit]
                current_start = None
            continue
    if strict and num > 0:
        raise Exception("parse error: unmatched '{' at position %s" % current_start)
    return parts[:limit]


_DEFAULT_ENCODING = "utf-8"


def _color_text(text, color):
    """
    Returns a string wrapped in ANSI color codes for coloring the
    text in a terminal::

        colored_text = color_text('Here is a message', 'blue')

    This won't actually effect the text until it is printed to the
    terminal.

    Parameters
    ----------
    text : str
        The string to return, bounded by the color codes.

    color : str
        An ANSI terminal color name. Must be one of:
        black, red, green, brown, blue, magenta, cyan, lightgrey,
        default, darkgrey, lightred, lightgreen, yellow, lightblue,
        lightmagenta, lightcyan, white, or '' (the empty string).

    Returns
    -------
    txt: str
        formatted text
    """
    color_mapping = {
        "black": "0;30",
        "red": "0;31",
        "green": "0;32",
        "brown": "0;33",
        "blue": "0;34",
        "magenta": "0;35",
        "cyan": "0;36",
        "lightgrey": "0;37",
        "default": "0;39",
        "darkgrey": "1;30",
        "lightred": "1;31",
        "lightgreen": "1;32",
        "yellow": "1;33",
        "lightblue": "1;34",
        "lightmagenta": "1;35",
        "lightcyan": "1;36",
        "white": "1;37",
    }

    if sys.platform == "win32":
        # On Windows do not colorize text unless in IPython
        return text

    color_code = color_mapping.get(color, "0;39")
    return "\033[{0}m{1}\033[0m".format(color_code, text)


def _decode_preferred_encoding(s):
    """Decode the supplied byte string using the preferred encoding
    for the locale (`locale.getpreferredencoding`) or, if the default encoding
    is invalid, fall back first on utf-8, then on latin-1 if the message cannot
    be decoded with utf-8.
    """
    enc = locale.getpreferredencoding()
    try:
        try:
            return s.decode(enc)
        except LookupError:
            enc = _DEFAULT_ENCODING
        return s.decode(enc)
    except UnicodeDecodeError:
        return s.decode("latin-1")


def _write_with_fallback(s, write, fileobj):
    """Write the supplied string with the given write function like
    ``write(s)``, but use a writer for the locale's preferred encoding in case
    of a UnicodeEncodeError.  Failing that attempt to write with 'utf-8' or
    'latin-1'.
    """
    try:
        write(s)
        return write
    except UnicodeEncodeError:
        pass

    enc = locale.getpreferredencoding()
    try:
        Writer = codecs.getwriter(enc)
    except LookupError:
        Writer = codecs.getwriter(_DEFAULT_ENCODING)

    f = Writer(fileobj)
    write = f.write

    try:
        write(s)
        return write
    except UnicodeEncodeError:
        Writer = codecs.getwriter("latin-1")
        f = Writer(fileobj)
        write = f.write

    write(s)
    return write


def color_print(*args, **kwargs):
    """
    Prints colors and styles to the terminal uses ANSI escape
    sequences.

    ::

       color_print('This is the color ', 'default', 'GREEN', 'green')

    Parameters
    ----------
    positional args : str
        The positional arguments come in pairs (*msg*, *color*), where
        *msg* is the string to display and *color* is the color to
        display it in.

        *color* is an ANSI terminal color name.  Must be one of:
        black, red, green, brown, blue, magenta, cyan, lightgrey,
        default, darkgrey, lightred, lightgreen, yellow, lightblue,
        lightmagenta, lightcyan, white, or '' (the empty string).

    file : writeable file-like object, optional
        Where to write to.  Defaults to `sys.stdout`.  If file is not
        a tty (as determined by calling its `isatty` member, if one
        exists), no coloring will be included.

    end : str, optional
        The ending of the message.  Defaults to ``\\n``.  The end will
        be printed after resetting any color or font state.
    """

    file = kwargs.get("file", sys.stdout)
    end = kwargs.get("end", "\n")
    sep = kwargs.get("sep", " ")

    write = file.write

    if file.isatty():
        for i in range(0, len(args), 2):
            msg = args[i]
            if i + 1 == len(args):
                color = ""
            else:
                color = args[i + 1]

            if color:
                msg = _color_text(msg, color)

            """
            # Some file objects support writing unicode sensibly on some Python
            # versions; if this fails try creating a writer using the locale's
            # preferred encoding. If that fails too give up.
            if not PY3 and isinstance(msg, bytes):
                msg = _decode_preferred_encoding(msg)
            """

            write = _write_with_fallback(msg + sep, write, file)

        write(end)
    else:
        for i in range(0, len(args), 2):
            msg = args[i]
            """
            if not PY3 and isinstance(msg, bytes):
                # Support decoding bytes to unicode on Python 2; use the
                # preferred encoding for the locale (which is *sometimes*
                # sensible)
                msg = _decode_preferred_encoding(msg)
            """
            write(msg)
        write(end)


def tex_escape(text):
    """Escape latex special characters in one string

    Parameters
    ----------
    text: str
        a plain text message

    return
    ------
    newtext: str
        the message escaped to appear correctly in LaTeX
    """
    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\^{}",
        "\\": r"\textbackslash{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
        "\n": r""
    }
    regex = re.compile(
        "|".join(
            re.escape(key) for key in sorted(conv.keys(), key=lambda item: -len(item))
        )
    )
    return regex.sub(lambda match: conv[match.group()], text)


def get_latex_body(data):
    """Extract document body text"""
    start = re.compile(r"begin{document}").search(data).span()[1]
    end = re.compile(r"end{document}").search(data).span()[0]
    return clear_comments(data[start:end])


def get_latex_header(data):
    """Extract document header"""
    end = re.compile(r"begin{document}").search(data).span()[1]
    return data[:end]


def get_latex_macros(data):
    """Extract defined commands in the document header"""
    header = get_latex_header(data)
    macros = "\n".join(re.compile(r"command{.*}").findall(header))
    macros = macros.replace("command", "\\providecommand")
    macros = macros.replace("\\new\\provide", "\n\\provide")
    macros = macros.replace("\\provide\\provide", "\n\\provide")
    # multiline def will be ignored
    defs = [
        k for k in re.compile(r"\\def.*").findall(header) if len(balanced_braces(k)) > 0
    ]
    # some use \gdef  (global def instead of scoped)
    defs = defs + [
        k
        for k in re.compile(r"\\gdef.*").findall(header)
        if len(balanced_braces(k)) > 0
    ]
    defs = defs + [
        k
        for k in re.compile(r"\\graphicspath.*").findall(header)
        if len(balanced_braces(k)) > 0
    ]
    macros += "\n".join(defs)
    return macros


def clear_comments(data):
    """clean text from any comment"""
    lines = []
    for line in data.splitlines():
        mo = re.match(r"^((?:\\.|[^\\%]|\\$)*)(%.*)?$", line)
        if mo is None:
            raise Exception("regex failed %r" % (line,))
        lines.append(mo.group(1))
    return "\n".join(lines)


def get_latex_figures(data):
    """Extract figure declarations"""
    it = re.finditer(r"\\\\|(\\(begin|end){figure\*?})", data)
    open_figure = None
    figures = []
    for mo in it:
        if mo.group(0) == "\\\\":
            continue
        begin_or_end = mo.group(2)
        assert begin_or_end in ("begin", "end")
        if begin_or_end == "begin":
            # \begin{figure}
            if open_figure is not None:
                raise Exception("Unsupported: begin{figure} inside begin{figure}")
            open_figure = mo.start(1)
        else:
            # \end{figure}
            if open_figure is None:
                raise Exception(
                    "Unsupported: end{figure} without matching begin{figure}"
                )
            figures.append(data[open_figure : mo.end(1)])
            open_figure = None
    return figures


def parse_command(command, code, tokens=1):
    """
    Parse code to find a command arguments

    Parameters
    ----------
    command: str
        command to find

    code: str
        code in which searching

    tokens: int
        number of arguments to find

    Returns
    -------
    next_token: sequence or str
        found arguments
    """
    safe = command.replace("\\", "")
    # Match \<safe> followed by an optional argument
    pattern = r"\\%s\s*(?:\[[^]]*\]\s*)?" % safe
    mo = re.search(pattern, code)
    if mo is None:
        raise IndexError
    # where: position where the optional argument ends
    where = mo.end()
    next_token = balanced_braces(code[where:])[:tokens]
    if not next_token:
        print("parse_command(%r) did not find any arguments" % (command,))
    if tokens == 1:
        return next_token[0]
    return next_token


def parse_command_multi(command, code, tokens=1):
    """
    Parse code to find a command arguments and handles repeated command

    Parameters
    ----------
    command: str
        command to find

    code: str
        code in which searching

    tokens: int
        number of arguments to find

    Returns
    -------
    next_token: sequence or str
        found arguments
    """
    # command is a TeX command with or without leading backslash, e.g. input or \author
    assert re.match(r"^\\?[a-z]+$", command), command
    # Insert backslash in front of command if missing
    command = "\\" + command.strip("\\")
    pieces = [code[r.start() :] for r in re.finditer(re.escape(command), code)]
    ret = [parse_command(command, pk, tokens=tokens) for pk in pieces]
    assert len(ret) == code.count(command)
    return ret


def get_latex_environment(envname, data, onlycontent=True):
    """
    Parse code to find a specific environment content

    Parameters
    ----------
    envname: str
        environment to find

    data: str
        code in which searching

    onlycontent: bool, optional
        return only content otherwise incl. env. definition tags

    Returns
    -------
    content: sequence
        found content
    """
    if not onlycontent:
        starts = [k.span()[0] for k in re.compile(r"begin{" + envname).finditer(data)]
        ends = [
            k.span()[1] for k in re.compile(r"end{" + envname + ".*").finditer(data)
        ]
        content = [data[a - 1 : b] for a, b in zip(starts, ends)]
    else:
        starts = [k.span()[1] for k in re.compile(r"begin{" + envname).finditer(data)]
        ends = [
            k.span()[0] for k in re.compile(r"end{" + envname + ".*").finditer(data)
        ]
        content = [data[a + 1 : b - 1] for a, b in zip(starts, ends)]
    return content


class Figure(object):
    """
    class that attempts to catch figures from tex source input in many formats
    """

    def __init__(self, code, number=0):
        self._code = code
        self.info = self._parse()
        self._number = number
        self._n_references = 0

    def set_number_of_references(self, number):
        """tell how many times the figure is cited in the text"""
        self._n_references = number

    @property
    def number_of_references(self):
        """how many times the figure is cited in the text"""
        return self._n_references

    def _parse_subfigure(self):
        """Parse the code for specific commands"""
        commands = "caption", "label", "includegraphics", "plotone", "\\fig"
        info = {}
        # careful with subfigure...
        found = []
        for match in re.compile(r"subfigure.*").finditer(self._code):
            start, end = match.span()
            newcode = balanced_braces(self._code[start:end])[0]
            for command in commands:
                try:
                    found.append(parse_command(command, newcode))
                except IndexError:
                    pass
        info["subfigures"] = found

        for command in commands[:2]:
            try:
                info[command] = parse_command(command, self._code)
            except IndexError:
                info[command] = None

        return info

    def _parse(self):
        """Parse the code for specific commands"""
        commands = "caption", "label", "includegraphics", "plotone", "\\fig"
        info = {}
        # makes sure multiple includegraphics on the same line do work
        try:
            # careful with subfigure...
            if "subfigure" in self._code:
                return self._parse_subfigure()
            else:
                for command in commands:
                    count = self._code.count(command)
                    try:
                        if count > 1:
                            info[command] = parse_command_multi(command, self._code)
                        else:
                            info[command] = parse_command(command, self._code)
                    except IndexError:
                        info[command] = None
                command = "plottwo"
                try:
                    info[command] = parse_command(command, self._code, 2)
                except IndexError:
                    info[command] = None
        except Exception as error:
            print(error)
            # Catch any issue for now
            for command in commands:
                info[command] = None

        return info

    @property
    def files(self):
        """Associated data files"""
        files = []
        attr = self.info.get("plotone")

        def remove_specials(string):
            return string.replace("{", "").replace("}", "")

        if attr is not None:
            if isinstance(attr, basestring):
                files.append(remove_specials(attr))
            else:
                files.extend(attr)
        attr = self.info.get(r"\fig")
        if attr is not None:
            if isinstance(attr, basestring):
                files.append(attr)
            else:
                files.extend(attr)
        attr = self.info.get("includegraphics")
        if attr is not None:
            if isinstance(attr, basestring):
                files.append(remove_specials(attr))
            else:
                files.extend(attr)
        for k in "plottwo", "subfigures":
            attr = self.info.get(k)
            if attr is not None:
                files.extend(attr)
        return files

    @property
    def label(self):
        """figure label"""
        return self.info["label"]

    @property
    def caption(self):
        """figure caption"""
        return self.info["caption"]

    def __repr__(self):
        txt = """Figure {0:d} ({1:s})
        {2:s}
        File(s): {3:s}"""
        return txt.format(
            self._number, self.label or "", self.caption, ",".join(self.files)
        )


def get_short_authors(authors_list: list[str], highlight_authors: list[str]) -> str:
    if any(name in authors_list[0] for name in self.highlight_authors):
        authors = r"\hl{" + authors_list[0] + r"}, et al."
    else:
        authors = authors_list[0] + ", et al."
    if self.highlight_authors:
        incl_authors = []
        for name in self.highlight_authors:
            if name != authors_list[0]:
                incl_authors.append(r"\hl{" + name + r"}")
        authors += "; incl. " + ", ".join(incl_authors)
    return authors


class Document(object):
    """Latex Document structure"""

    def __init__(self, data):
        self._data = data
        self._code = self._clean_latex_comments(data)
        self._header = get_latex_header(self._code)
        self._body = get_latex_body(self._code)
        self._macros = get_latex_macros(self._header)
        self._title = None
        self._abstract = None
        self._authors: list[str] | None = None
        self._short_authors: str | None = None
        self._structure = None
        self._identifier = None
        self.figures = [
            Figure(k, e) for e, k in enumerate(get_latex_figures(self._body), 1)
        ]
        self.highlight_authors = []
        self.comment = None
        self.date = ""

        self._update_figure_references()

    def _clean_latex_comments(self, code):
        return re.sub(r"(?<!\\)%.*\n", "", code)

    def _update_figure_references(self):
        """parse to find cited figures in the text"""
        for fig in self.figures:
            if fig.label is not None:
                try:
                    number = len(
                        re.compile(r"\\ref{" + fig.label + "}").findall(self._code)
                    )
                    fig.set_number_of_references(number)
                except TypeError:
                    # sometimes labels are duplicated into a list
                    number = len(
                        re.compile(r"\\ref{" + fig.label[0] + "}").findall(self._code)
                    )
                    fig.set_number_of_references(number)

    @property
    def arxivertag(self):
        """check for arxiver tag selecting figures"""
        tags = None
        if r"%@arxiver" in self._data:
            start, end = list(re.compile(r"@arxiver{.*}").finditer(self._data))[
                0
            ].span()
            tags = balanced_braces(self._data[start:end])[0]
            color_print("*** arxiver figure tag", "green")
        return tags

    @property
    def title(self):
        """Document title"""
        if self._title is None:
            self._title = parse_command("title", self._code)
        return self._title

    @property
    def authors(self) -> list[str]:
        """Document authors"""
        if self._authors is None:
            # self._authors = parse_command('author', self._code)
            self._authors = parse_command_multi("author", self._code)
        return self._authors

    @property
    def short_authors(self) -> str:
        """Short authors"""
        if self._short_authors is not None:
            return self._short_authors
        authors_list = self.authors
        assert not isinstance(authors_list, basestring)
        self._short_authors = get_short_authors(authors_list, self.highlight_authors)
        return self._short_authors

    @property
    def abstract(self):
        """Document abstract"""
        if self._abstract is None:
            try:
                try:
                    # AA abstract
                    self._abstract = "\n".join(parse_command("abstract", self._body, 5))
                except Exception as error:
                    self._abstract = parse_command("abstract", self._code)
            except IndexError:
                self._abstract = " ".join(get_latex_environment("abstract", self._code))
        # Cleaning
        self._abstract = "\n".join([k for k in self._abstract.splitlines() if k != ""])
        return self._abstract

    def _parse_structure(self):
        if self._structure is not None:
            return self._structure

        tags = list(re.compile(r"\\([^\s]*)section").finditer(self._body))
        try:
            appendix_start = list(
                re.compile(r"\\([^\s]*)appendix").finditer(self._body)
            )[0].span()[1]
        except IndexError:
            appendix_start = len(self._code)
        structure = []
        levels = {r"\section": 0, "\subsection": 1, "\subsubsection": 2}
        for tag in tags:
            starts = tag.span()[0]
            name = parse_command(tag.group(), self._code[starts:])
            level = levels[tag.group()] + int(starts >= appendix_start)
            attr = (level, name, [])

            if not structure:
                structure.append(attr)
            else:
                if (starts >= appendix_start) & (structure[-1][1] != "Appendix"):
                    structure.append((0, "Appendix", []))
                if level > structure[-1][0]:
                    last = structure[-1][-1]
                    if last:
                        if level > last[-1][0]:
                            last[-1][-1].append(attr)
                        else:
                            structure[-1][-1].append(attr)
                    else:
                        structure[-1][-1].append(attr)
                else:
                    structure.append(attr)
        self._structure = structure
        return self._structure

    def print_structure(self):
        """Pretty print the document structure"""
        for node in self._parse_structure():
            name = node[1]
            children = node[-1]
            print(name)
            for subnode in children:
                name = subnode[1]
                print("  " * subnode[0], name)
                for subsubnode in subnode[-1]:
                    print("  " * subsubnode[0], subsubnode[1])

    def __repr__(self):
        txt = """{s.title:s}\n\t{s.short_authors:s}"""
        if self._identifier:
            txt = """[{s._identifier:s}]: """ + txt
        return txt.format(s=self)


class ExportCompileTemplate(Protocol):
    def apply_to_document(self, document: "DocumentSource") -> str:
        ...

    compiler: str
    compiler_options: str


class ExportPDFLatexTemplate(object):
    """default template"""

    template = r"""%
\documentclass[a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[a4paper,margin=.5cm,landscape]{geometry}
\usepackage[english]{babel}
\usepackage{natbib}
\usepackage{graphicx}
\usepackage{txfonts}
\usepackage{xcolor}
\usepackage{amsfonts}
\usepackage{mathrsfs}
\usepackage{amssymb}
\usepackage{textgreek}
\usepackage[nolist,nohyperlinks,printonlyused]{acronym}
\usepackage[breaklinks,colorlinks,citecolor=blue,unicode]{hyperref}
\usepackage{siunitx}
\usepackage[Symbol]{upgreek}

\DeclareRobustCommand{\ion}[2]{\textup{#1\,\textsc{\lowercase{#2}}}}
\newcommand*\element[1][]{%
  \def\aa@element@tr{#1}%
  \aa@element
}

%convert files on the fly to pdflatex compilation
\DeclareGraphicsExtensions{.jpg, .ps, .eps, .png, .pdf}
\DeclareGraphicsRule{.ps}{pdf}{.pdf}{`convert #1 pdf:`dirname #1`/`basename #1 .ps`-ps-converted-to.pdf}
\DeclareGraphicsRule{.eps}{pdf}{.pdf}{`convert #1 pdf:`dirname #1`/`basename #1 .eps`-eps-converted-to.pdf}

%Document found macros
<MACROS>

% template macros
\renewcommand{\abstract}[1]{%
  \textbf{<IDENTIFIER> } #1
}
\newcommand\hl[1]{\colorbox{yellow}{#1}}

\renewcommand{\thanks}[1]{}
\renewcommand{\caption}[1]{{\scriptsize{#1}}}
\providecommand{\acronymused}[1]{}
\providecommand{\altaffilmark}[1]{}

\begin{document}
\thispagestyle{plain}
\begin{minipage}[t][0pt]{0.98\linewidth}

\textbf{\LARGE{<TITLE>}}

\vspace{1em}

\textbf{\large{<AUTHORS>}}

\vspace{1em}

\abstract{
<ABSTRACT>
}

\vspace{1em}

\centering
<FIGURES>

\vfill
\hl{<DATE>} -- <COMMENTS>
\end{minipage}

\end{document}
"""

    compiler = r"TEXINPUTS='{0:s}/deprecated_tex:' pdflatex ".format(__ROOT__)
    compiler_options = r" -interaction=batchmode "

    def short_authors(self, document):
        """Short author"""
        return document.short_authors

    def select_figures(self, document, N=3):
        """decides which figures to show"""
        try:
            if document.arxivertag:
                selected = {
                    fig.files[0]: fig
                    for fig in document.figures
                    if fig.files[0] in document.arxivertag
                }
                return [
                    selected[fname]
                    for fname in document.arxivertag.replace(",", " ").split()
                ]  ## Keep the same ordering
        except Exception as e:
            raise_or_warn(e)

        selection = sorted(
            document.figures, key=lambda x: x.number_of_references, reverse=True
        )
        return selection[:N]

    def figure_to_latex(self, figure, size=r"0.32\textwidth") -> str:
        """makes the figures in tex formatting"""
        txt = r"""\begin{minipage}{0.32\textwidth}""" + "\n"
        for fname in figure.files:
            txt += r"    \includegraphics[width=\textwidth, height=0.4\textheight,keepaspectratio]{"
            txt += fname + r"}\\" + "\n"
        txt += (
            r"""    \caption{Fig. """
            + str(figure._number)
            + """: """
            + figure.caption
            + r"""}"""
        )
        txt += "\n" + """\end{minipage}""" + "\n%\n"
        return txt

    def apply_to_document(self, document):
        """generate tex code from document"""

        txt = self.template.replace("<MACROS>", "")  # document._macros)
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
        figures = "".join(
            [self.figure_to_latex(fig) for fig in self.select_figures(document)]
        )
        txt = txt.replace("<FIGURES>", figures)
        txt = txt.replace("<COMMENTS>", tex_escape(document.comment) or "")
        txt = txt.replace("<DATE>", document.date)

        return txt


class DocumentSource(Document):
    """Source code class"""

    def __init__(self, directory, autoselect=True):
        fnames = glob(directory + "/*.tex")
        if autoselect:
            fname = self._auto_select_main_doc(fnames)
        else:
            fname = self._manual_select_main_doc(fnames)

        with open(fname, "r", errors="surrogateescape") as finput:
            data = finput.read()
            if "\input" and ".tex" in data:
                for input_command in ["input", "include"]:
                    data = self._expand_auxilary_files(
                        data, directory=directory, command=input_command
                    )
            data = self._parse_of_import_package(data, directory=directory)

        Document.__init__(self, data)
        self.fname = fname
        self.directory = directory
        self.outputname = self.fname[: -len(".tex")] + "_cleaned.tex"

    def _parse_of_import_package(self, data, directory="", debug=False):
        if not r"usepackage{import}" in data:
            return data
        command = "import"
        inputs = list(re.compile(r"\\{0:s}.*".format(command)).finditer(data))
        if len(directory):
            if directory[-1] != "/":
                directory = directory + "/"
        if len(inputs) > 0:
            if debug:
                print("*** Found document inclusions using import ")
            new_data = []
            prev_start, prev_end = 0, 0
            for match in inputs:
                try:
                    fname = match.group().replace(r"\import", "").strip()
                    fname = (
                        fname.replace("{", "").replace("}", "").replace(".tex", "")
                    )  # just in case
                    if debug:
                        print("      input command: ", fname)
                    try:
                        with open(
                            directory + fname + ".tex", "r", errors="surrogateescape"
                        ) as fauxilary:
                            auxilary = fauxilary.read()
                    except:
                        with open(
                            directory + fname, "r", errors="surrogateescape"
                        ) as fauxilary:
                            auxilary = fauxilary.read()
                    start, end = match.span()
                    new_data.append(data[prev_end:start])
                    new_data.append(
                        "\n%input from {0:s}\n".format(fname) + auxilary + "\n"
                    )
                    prev_start, prev_end = start, end
                except Exception as e:
                    raise_or_warn(e)
            new_data.append(data[prev_end:])
            return "\n".join(new_data)
        else:
            return data

    def _expand_auxilary_files(self, data, directory="", command="input", debug=False):
        # inputs
        inputs = list(re.finditer(r"\\%s\{.*" % re.escape(command), data))
        if len(directory):
            if directory[-1] != "/":
                directory = directory + "/"
        if len(inputs) > 0:
            if debug:
                print("*** Found document inclusions ")
            new_data = []
            prev_start, prev_end = 0, 0
            for match in inputs:
                try:
                    fname = match.group().replace("\\" + command, "").strip()
                    fname = (
                        fname.replace("{", "").replace("}", "").replace(".tex", "")
                    )  # just in case
                    if debug:
                        print("      input command: ", fname)
                    with open(
                        directory + fname + ".tex", "r", errors="surrogateescape"
                    ) as fauxilary:
                        auxilary = fauxilary.read()
                    start, end = match.span()
                    new_data.append(data[prev_end:start])
                    new_data.append(
                        "\n%input from {0:s}\n".format(fname) + auxilary + "\n"
                    )
                    prev_start, prev_end = start, end
                except Exception as e:
                    raise_or_warn(e)
            new_data.append(data[prev_end:])
            return "\n".join(new_data)
        else:
            return data

    def _auto_select_main_doc(self, fnames, debug=False):
        if len(fnames) == 1:
            return fnames[0]

        selected = None
        for e, fname in enumerate(fnames):
            if "mnras_guide" in fname:
                continue
            with open(fname, "r", errors="surrogateescape") as finput:
                s = finput.read()
                if ("documentclass" in s) and (r"\title" in s):
                    selected = e, fname
                    break
        if debug:
            print("Found main document: ", selected)
        if selected is not None:
            return selected[1]
        else:
            print(
                "Could not locate the main document automatically. Little help please!"
            )
            return self._manual_select_main_doc(fnames)

    def _manual_select_main_doc(self, fnames):
        """Manual selection of the file that is the main tex document"""
        for e, fname in enumerate(fnames):
            print(e, fname)
        select = input("which file is the main document? ")
        return fnames[int(select)]

    def __repr__(self):
        return """Paper in {0:s}, \n\t{1:s}""".format(
            self.fname, Document.__repr__(self)
        )

    def compile(self, template: ExportCompileTemplate | None = None):

        if template is None:
            template = ExportPDFLatexTemplate()

        data = template.apply_to_document(self)

        compile_template_with_aux_from_source(
            compiler=template.compiler,
            compiler_options=template.compiler_options,
            directory=self.directory,
            fname=self.fname,
            outputname=self.outputname,
            data=data,
        )


def compile_template_without_source(
    compiler: str,
    compiler_options: str,
    directory: str,
    outputname: str,
    data: str,
) -> None:
    with open(outputname, "w") as out:
        out.write(
            data.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        )
    compiler_command = "cd {0:s}; {1:s} {2:s} ".format(
        directory, compiler, compiler_options
    )
    outputname = outputname.split("/")[-1]
    subprocess.call(
        compiler_command + outputname, shell=True, stdin=subprocess.DEVNULL
    )


def compile_template_with_aux_from_source(
    compiler: str,
    compiler_options: str,
    directory: str,
    fname: str,
    outputname: str,
    data: str,
) -> None:

    with open(outputname, "w") as out:
        out.write(
            data.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        )

    # compile source to get aux data if necessary
    compiler_command = "cd {0:s}; {1:s} {2:s} ".format(
        directory, compiler, compiler_options
    )
    if not os.path.isfile(fname.replace(".tex", ".aux")):
        fname = fname.split("/")[-1]
        subprocess.call(
            compiler_command + fname, shell=True, stdin=subprocess.DEVNULL
        )

    # get the references compiled
    input_aux = fname.replace(".tex", ".aux")
    output_aux = outputname.replace(".tex", ".aux")
    try:
        with open(output_aux, "w+") as fout:
            with open(input_aux, "r", errors="surrogateescape") as fin:
                for line in fin:
                    if (
                        ("cite" in line)
                        or ("citation" in line)
                        or ("label" in line)
                        or ("toc" in line)
                    ):
                        fout.write(
                            line.encode("utf-8", "surrogateescape").decode(
                                "utf-8", "replace"
                            )
                        )
    except Exception:
        pass

    # compile output
    outputname = outputname.split("/")[-1]
    subprocess.call(
        compiler_command + outputname, shell=True, stdin=subprocess.DEVNULL
    )


class ArxivListHTMLParser(HTMLParser):
    """generates a list of Paper items by parsing the Arxiv new page"""

    def __init__(self, *args, **kwargs):
        skip_replacements = kwargs.pop("skip_replacements", False)
        HTMLParser.__init__(self, *args, **kwargs)
        self.papers = []
        self.current_paper = None
        self._paper_item = False
        self._title_tag = False
        self._author_tag = False
        self.skip_replacements = skip_replacements
        self._skip = False
        self._date = kwargs.pop("appearedon", "")

    def handle_starttag(self, tag, attrs):
        # paper starts with a dt tag
        if tag in ("dt") and not self._skip:
            if self.current_paper:
                self.papers.append(self.current_paper)
            self._paper_item = True
            self.current_paper = ArXivPaper(appearedon=self._date)

    def handle_endtag(self, tag):
        # paper ends with a /dd tag
        if tag in ("dd"):
            self._paper_item = False
        if tag in ("div",) and self._author_tag:
            self._author_tag = False
        if tag in ("div",) and self._title_tag:
            self._title_tag = False

    def handle_data(self, data):
        if data.strip() in (None, "", ","):
            return
        if "replacements for" in data.lower():
            self._skip = True & self.skip_replacements
        if "new submissions for" in data.lower():
            self._date = data.lower().replace("new submissions for", "")
        if self._paper_item:
            if "arXiv:" in data:
                self.current_paper.identifier = data
            if self._title_tag:
                self.current_paper.title = data.replace("\n", "")
                self._title_tag = False
            if self._author_tag:
                self.current_paper._authors.append(data.replace("\n", ""))
                self._title_tag = False
            if "Title:" in data:
                self._title_tag = True
            if "Authors:" in data:
                self._author_tag = True


class ArXivPaper(object):
    """Class that handles the interface to Arxiv website paper abstract"""

    source = "https://arxiv.org/e-print/{identifier}"

    def __init__(self, identifier="", highlight_authors=None, appearedon=None):
        """Initialize the data"""
        self.identifier = identifier
        self.title = ""
        self._authors = []
        if highlight_authors is None:
            self.highlight_authors = []
        else:
            self.highlight_authors = highlight_authors
        self.comment = ""
        self.date = None
        self.appearedon = appearedon
        if len(self.identifier) > 0:
            self.get_abstract()

    @classmethod
    def from_identifier(cls, identifier):
        return cls(identifier.split(":")[-1]).get_abstract()

    @property
    def authors(self):
        authors = ", ".join(self._authors)
        if len(self.highlight_authors) > 0:
            for name in self.highlight_authors:
                if name in authors:
                    authors = authors.replace(name, r"\hl{" + name + r"}")
        return authors

    @property
    def short_authors(self):
        if len(self.authors) < 5:
            return self.authors
        else:
            if any(name in self._authors[0] for name in self.highlight_authors):
                authors = r"\hl{" + self._authors[0] + r"}, et al."
            else:
                authors = self._authors[0] + ", et al."
        if len(self.highlight_authors) > 0:
            incl_authors = []
            for name in self.highlight_authors:
                if name != self._authors[0]:
                    incl_authors.append(r"\hl{" + name + r"}")
            authors += "; incl. " + ", ".join(incl_authors)
        return authors

    def __repr__(self):
        txt = """[{s.identifier:s}]: {s.title:s}\n\t{s.authors:s}"""
        return txt.format(s=self)

    def retrieve_document_source(self, directory, autoselect=True) -> DocumentSource | None:
        where = ArXivPaper.source.format(identifier=self.identifier.split(":")[-1])
        try:
            tar = tarfile.open(mode="r|gz", fileobj=urlopen(where))
        except Exception as error:
            print("PDF only?")
            return None

        assert directory is not None
        if os.path.isdir(directory):
            shutil.rmtree(directory)
        tar.extractall(directory)
        document = DocumentSource(directory, autoselect=autoselect)
        self.get_abstract()
        try:
            document.authors
        except Exception as error:
            raise_or_warn(error)
            document._authors = self.authors
        try:
            document.abstract
        except Exception as error:
            raise_or_warn(error)
            document._abstract = self.abstract
        document._short_authors = self.short_authors
        document._authors = self.authors
        document._identifier = self.identifier
        document.comment = None
        if self.comment:
            document.comment = self.comment.replace("\\ ", " ")
            document.comment = self.comment

        if self.appearedon in (None, "", "None"):
            document.date = self.date
        else:
            document.date = "Appeared on " + self.appearedon
        return document

    def get_abstract(self):
        where = "https://export.arxiv.org/api/query?id_list={}".format(self.identifier.split(":")[-1])
        with urlopen(where) as resp:
            the_xml = resp.read().decode("utf-8")
        doc = ET.fromstring(the_xml)
        assert doc.tag == '{http://www.w3.org/2005/Atom}feed', where
        entry = doc.find('{http://www.w3.org/2005/Atom}entry')
        assert entry is not None, where
        summary_tag = entry.find('{http://www.w3.org/2005/Atom}summary')
        assert summary_tag is not None, where
        abstract = summary_tag.text

        title_tag = entry.find('{http://www.w3.org/2005/Atom}title')
        assert title_tag is not None, where
        title = title_tag.text or ""

        author_tags = entry.findall('{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')
        authors = [t.text or "" for t in author_tags]

        comment_tag = entry.find('{http://arxiv.org/schemas/atom}comment')
        # assert comment_tag is not None
        if comment_tag is None:
            comment = ""
        else:
            comment = comment_tag.text or ""

        published_tag = entry.find('{http://www.w3.org/2005/Atom}published')
        assert published_tag is not None
        assert published_tag.text
        date_dt = datetime.datetime.fromisoformat(published_tag.text.replace("Z", "+00:00"))

        self.title = title
        self._authors = authors
        self.abstract = abstract
        self.comment = tex_escape(comment)
        self.date = date_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        return self

    def make_postage(self, template=None):
        print("Generating postage")
        self.get_abstract()
        s = self.retrieve_document_source(__ROOT__ + "/tmp")
        s.compile(template=template)
        identifier = self.identifier.split(":")[-1]
        name = s.outputname.replace(".tex", ".pdf").split("/")[-1]
        shutil.copy2(__ROOT__ + "/tmp/" + name, identifier + ".pdf")
        shutil.copy2(__ROOT__ + "/" + name, identifier + ".pdf")
        print("PDF postage:", identifier + ".pdf")


def get_new_papers(skip_replacements=True, appearedon=None):
    """retrieve the new list from the website
    Parameters
    ----------
    skip_replacements: bool
        set to skip parsing the replacements

    Returns
    -------
    papers: list(ArXivPaper)
        list of ArXivPaper objects
    """
    where = "https://rss.arxiv.org/atom/astro-ph"
    with urlopen(where) as resp:
        the_xml = resp.read().decode("utf-8")
    doc = ET.fromstring(the_xml)
    assert doc.tag == '{http://www.w3.org/2005/Atom}feed', doc.tag
    entries = doc.findall('{http://www.w3.org/2005/Atom}entry')
    assert entries
    papers: list[ArXivPaper] = []
    for entry in entries:
        id_tag = entry.find('{http://www.w3.org/2005/Atom}id')
        assert id_tag is not None, where
        the_id = id_tag.text
        assert the_id is not None
        assert the_id.startswith("oai:")
        the_id = the_id.partition("oai:")[2]

        # summary_tag = entry.find('{http://www.w3.org/2005/Atom}summary')
        # assert summary_tag is not None, where
        # abstract = summary_tag.text

        title_tag = entry.find('{http://www.w3.org/2005/Atom}title')
        assert title_tag is not None, where
        title = title_tag.text or ""

        authors = entry.find('{http://purl.org/dc/elements/1.1/}creator')
        authors_text = authors.text
        assert authors_text is not None
        authors = authors_text.split(", ")

        # comment_tag = entry.find('{http://arxiv.org/schemas/atom}comment')
        # if comment_tag is None:
        #     comment = ""
        # else:
        #     comment = comment_tag.text or ""

        # published_tag = entry.find('{http://www.w3.org/2005/Atom}published')
        # assert published_tag is not None
        # assert published_tag.text
        # date_dt = datetime.datetime.fromisoformat(published_tag.text.replace("Z", "+00:00"))

        paper = ArXivPaper()
        paper.identifier = the_id
        paper.title = title
        for author in authors:
            paper._authors.append(author)
        papers.append(paper)
    return papers


def get_catchup_papers(since=None, skip_replacements=False, appearedon=None):
    """retrieve the new list from the website
    Parameters
    ----------
    since: string
        data to start from
    skip_replacements: bool
        set to skip parsing the replacements

    Returns
    -------
    papers: list(ArXivPaper)
        list of ArXivPaper objects
    """
    from datetime import datetime, date

    if since is None:
        since = date.today().strftime("%d/%m/%y")
    elif "today" in since.lower():
        since = date.today().strftime("%d/%m/%y")

    try:
        # dd/mm/yy
        _since = datetime.strptime(since, "%d/%m/%y")
    except ValueError:
        # dd/mm/yyyy
        _since = datetime.strptime(since, "%d/%m/%Y")

    print("after", _since)
    url = "https://arxiv.org/catchup?syear={year:d}&smonth={month:d}&sday={day:d}&num=1000&archive=astro-ph&method=without"
    html = (
        urlopen(url.format(day=_since.day, month=_since.month, year=_since.year))
        .read()
        .decode("utf-8")
    )

    parser = ArxivListHTMLParser(skip_replacements=skip_replacements)
    parser.feed(html)
    papers = parser.papers
    return papers


def get_coworker(source=__ROOT__ + "/coworker.txt"):
    """returns the list of authors of interests.
    Needed to parse the input list to get initials and last name.
    This may not work all the time. The best would be to have the proper names
    directly given as e.g. "I.-M. Groot".

    Returns
    -------
    coworker: list(str)
       authors to look for
    """
    with open(source, errors="surrogateescape") as fin:
        coworker = []
        for name in fin:
            if name[0] != "#":  # Comment line
                names = name.split()
                shortname = []
                for name in names[:-1]:
                    if "-" in name:
                        rest = "-".join([w[0] + "." for w in name.split("-")])
                    else:
                        rest = name[0] + "."
                    shortname.append(rest)
                shortname.append(names[-1])
                coworker.append(" ".join(shortname))
    return list(sorted(set(coworker)))


def highlight_papers(papers: list[ArXivPaper], fname_list: list[str]) -> tuple[list[ArXivPaper], list[tuple[str, str, str]]]:
    """Extract papers when an author match is found

    Parameters
    ----------
    papers: list(ArXivPaper)
        paper list
    fname_list: list(str)
        authors to search

    Returns
    -------
    keep: list(ArXivPaper)
        papers with matching author
    """
    keep: list[ArXivPaper] = []
    matched_authors: list[tuple[str, str, str]] = []
    for paper in papers:
        print(paper)
        paper.highlight_authors = []
        for author in paper._authors:
            for name in fname_list:
                if name in author:
                    # perfect match on family name
                    # TODO: add initials test
                    if name == author.split()[-1]:
                        print("*** Matching author: ", name, author)
                        matched_authors.append((name, author, paper.identifier))
                        paper.highlight_authors.append(author)
        keep.append(paper)
    return keep, matched_authors


def filter_papers(papers, fname_list):
    """Extract papers when an author match is found
    Parameters
    ----------
    papers: list(ArXivPaper)
        paper list
    fname_list: list(str)
        authors to search

    Returns
    -------
    keep: list(ArXivPaper)
        papers with matching author
    """
    keep = []
    matched_authors = []
    for paper in papers:
        paper.highlight_authors = []
        matches = [name for name in fname_list if " " + name in paper.authors]
        if matches:
            for author in paper._authors:
                for name in fname_list:
                    if name in author:
                        # TODO: add initials test
                        if name == author.split()[-1]:
                            print("*** Matched author: ", name, author)
                            matched_authors.append((name, author, paper.identifier))
                            paper.highlight_authors.append(author)
                            keep.append(paper)
    return keep, matched_authors


def check_required_words(source, word_list=[], verbose=False):
    """Check the paper for words required for processing

    Test is case insensitive but all words must appear
    """
    for word in word_list:
        if (word in source._code) or (word.lower() in source._code):
            pass
        else:
            if verbose:
                return "'{0:s}' keyword not found.".format(word)
            return False
    return True


def running_options():

    opts = (
        (
            "-s",
            "--source",
            dict(
                dest="sourcedir",
                help="Use an existing source directory",
                default="",
                type="str",
            ),
        ),
        (
            "-m",
            "--coworker",
            dict(
                dest="hl_authors",
                help="List of authors to highlight (co-workers)",
                default=__ROOT__ + "/coworker.txt",
                type="str",
            ),
        ),
        (
            "-i",
            "--id",
            dict(
                dest="identifier",
                help="Make postage of a single paper given by its arxiv id",
                default="None",
                type="str",
            ),
        ),
        (
            "-a",
            "--authors",
            dict(
                dest="hl_authors",
                help="Highlight specific authors",
                default="None",
                type="str",
            ),
        ),
        (
            "-d",
            "--date",
            dict(
                dest="date",
                help="Impose date on the printouts (e.g., today)",
                default="",
                type="str",
            ),
        ),
        (
            "-c",
            "--catchup",
            dict(
                dest="since",
                help="Catchup arxiv from given date (e.g., today, 03/01/2018)",
                default="",
                type="str",
            ),
        ),
        (
            "--selectfile",
            dict(
                dest="select_main",
                default=False,
                action="store_true",
                help="Set to select the main tex file manually",
            ),
        ),
        (
            "--debug",
            dict(
                dest="debug",
                default=False,
                action="store_true",
                help="Set to raise exceptions on errors",
            ),
        ),
    )

    from optparse import OptionParser

    parser = OptionParser()

    for ko in opts:
        parser.add_option(*ko[:-1], **ko[-1])

    (options, args) = parser.parse_args()

    __DEBUG__ = options.__dict__.get("debug", False)

    return options.__dict__


def check_date(datestr):
    if "today" in datestr.lower():
        import datetime

        return datetime.date.today().strftime("%d/%m/%y")
    elif len(datestr) == 0:
        return None
    else:
        return datestr


def main(template=None):
    options = running_options()
    identifier = options.get("identifier", None)
    sourcedir = options.get("sourcedir", None)
    catchup_since = options.get("since", None)
    select_main = options.get("select_main", False)

    coworker_list = options.get("coworker", __ROOT__ + "/coworker.txt")
    coworker = get_coworker(coworker_list)

    if sourcedir not in (None, ""):
        paper = DocumentSource(sourcedir, autoselect=(not select_main))
        paper.identifier = sourcedir
        keep, _ = highlight_papers([paper], coworker)
        paper.compile(template=template)
        name = paper.outputname.replace(".tex", ".pdf").split("/")[-1]
        shutil.move(sourcedir + "/" + name, paper.identifier + ".pdf")
        print("PDF postage:", paper.identifier + ".pdf")
        return
    elif identifier in (None, "", "None"):
        print("main", repr(catchup_since))
        if catchup_since not in (None, "", "None", "today"):
            papers = get_catchup_papers(since=catchup_since, skip_replacements=True)
        else:
            papers = get_new_papers(skip_replacements=True)
        keep, _ = filter_papers(papers, coworker)
    else:
        papers = [
            ArXivPaper(
                identifier=identifier.split(":")[-1],
                appearedon=check_date(options.get("date")),
            )
        ]
        keep, _ = highlight_papers(papers, coworker)

    for paper in keep:
        try:
            paper.make_postage(template=template)
        except Exception as error:
            raise_or_warn(error)
