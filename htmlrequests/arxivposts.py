import argparse
import re
from requests_html import HTMLSession
session = HTMLSession()

parser = argparse.ArgumentParser()
parser.add_argument('arxivid')
args = parser.parse_args()

arxivid = args.arxivid
arxivlink = 'https://arxiv.org/abs/' + arxivid
r = session.get(arxivlink)

# arxiv.org pages start with XML encoding declaration,
# and requests_html does not like that. Remove the encoding declaration.
r.html.html = re.sub(r'^<\?xml.*?\?>', '', r.html.html)

# Now find your page, find the value you want to extract, inspect element
# and copy selector and insert it in the string.
titles = r.html.find('#abs > h1')
titles, = titles
title = titles.text.replace('Title:', '')

# This finds the href blocks instantly
# TODO: Map name in dictionary, so the right childs are read
datadict = {}
for tr in r.html.find('#abs > div.metatable > table > tr'):
    key, data = tr.find('td')
    datadict[key.text] = data

pub = datadict['Comments:'].text
try:
    doi = datadict['DOI:'].text
    doi = 'https://dx.doi.org/' + doi
except:
    doi = arxivlink

abstracts, = r.html.find('#abs > blockquote')
abstract = abstracts.text.replace('Abstract: ', '')

# Fix in-line math with MathJax by replacing $ with \(\).
c = abstract.count('$')
#assert c % 2 == 0

# Replace every other occurance with the opposite parantheses
# https://stackoverflow.com/questions/46705546/python-replace-every-nth-occurrence-of-string
def nth_repl_all(s, sub, repl, nth):
    find = s.find(sub)
    # loop util we find no match
    i = 1
    while find != -1:
        # if i  is equal to nth we found nth matches so replace
        if i == nth:
            s = s[:find]+repl+s[find + len(sub):]
            i = 0
        # find + len(sub) + 1 means we start after the last match
        find = s.find(sub, find + len(sub) + 1)
        i += 1
    return s

abstract = nth_repl_all(abstract, '$', '\)', 2)
abstract = abstract.replace('$', '\([mathjax]', 1)
abstract = abstract.replace('$', '\(')


tpl = '''<p style="text-align: justify;">{authors}</p>
<p style="text-align: left;">
<strong><a class="link" href="{doi}"= target="_blank" rel="ContributionToJournal noopener">{title}</a>
</strong> <a class="link" href="{arxiv}"= target="_blank" rel="ContributionToJournal noopener">See arXiv version</a>
<em>{pub}</em>
</p>
<p style="text-align: justify;"><!--more--></p>

<p></p>
<h3 style="text-align: justify;"><strong>Abstract</strong></h3>
<p style="text-align: justify;">{abstract}</p>
'''

# typeset authors. if author is in isimba: boldface them.
authorss, = r.html.find('#abs > div.authors')
authors = authorss.find('a')
authorlist = []
authortpl = '<a href="{href}">{name}</a>'
for author in authors:
    href = 'https://arxiv.org' + author.attrs['href']
    a = authortpl.format(href=''.join(href.split()),
            name=author.text.replace(',',''))
    authorlist.append(a)

blogtext = tpl.format(authors=', '.join(authorlist),
                      doi=doi,
                      title=title,
                      pub=pub,
                      arxiv=arxivlink,
                      abstract=abstract,
                      )
print(blogtext)
f = open('blogpost.txt', 'w')
f.write(blogtext)
f.close()
