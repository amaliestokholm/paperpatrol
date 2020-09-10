from requests_html import HTMLSession
session = HTMLSession()

adslink = 'http://adsabs.harvard.edu/abs/2018AJ....155..100J'
#'http://adsabs.harvard.edu/abs/2018ASSP...49..149L' #'http://adsabs.harvard.edu/abs/2018ApJ...852...46K'
r = session.get(adslink)

# Now find your page, find the value you want to extract, inspect element
# and copy selector and insert it in the string.
titles, = r.html.find('body > table:nth-child(7) > tbody > tr:nth-child(1) > td:nth-child(3)')
title = titles.text

#authors, = r.html.find('body > table:nth-child(7) > tbody > tr:nth-child(2) > td:nth-child(3)')
#author = authors.text
#author_links = authors.links
#print(author)

# This finds the href blocks instantly
# TODO: Map name in dictionary, so the right childs are read
datadict = {}
for tr in r.html.find('body > table:nth-child(7) > tbody > tr'):
    key, empty, data = tr.find('td')
    print(key.text, data.text)
    datadict[key.text] = data

authors = datadict['Authors:'].find('a')
pub = datadict['Publication:'].text
try:
    kw = datadict['Astronomy Keywords:'].text.lower()
except KeyError:
    kw = datadict['Keywords:'].text.lower()
doi = datadict['DOI:'].text

"""
authors = r.html.find('body > table:nth-child(7) > tbody > tr:nth-child(2) > td:nth-child(3) > a')

publication, = r.html.find('body > table:nth-child(7) > tbody > tr:nth-child(4) > td:nth-child(3)')
pub = publication.text

kws, = r.html.find('body > table:nth-child(7) > tbody > tr:nth-child(7) > td:nth-child(3)')
kw = kws.text

dois, = r.html.find('body > table:nth-child(7) > tbody > tr:nth-child(8) > td:nth-child(3)')
doi = dois.text
"""

abstract_header, = r.html.find('body > h3:nth-child(8)')
abstract = abstract_header.element.tail
abstract = ' '.join(abstract.split())

tpl = '''<p style="text-align: justify;">{authors}</p>
<p style="text-align: left;">
<strong><a class="link" href="{doi}"= target="_blank" rel="ContributionToJournal noopener">{title}</a>
</strong>
<em>{journal}</em>, {vol}, {issue}</p>
<p style="text-align: justify;"><!--more--></p>

<h3 style="text-align: justify;"><strong>Abstract</strong></h3>
<p style="text-align: justify;">{abstract}</p>

<em>Keywords: {kw}</em>
'''

# typeset authors. if author is in isimba: boldface them.
authorlist = []
authortpl = '<a href="{href}">{name}</a>'
for author in authors:
    href = author.attrs['href']
    a = authortpl.format(href=''.join(href.split()), name=author.text)
    authorlist.append(a)

splitpub = pub.split(',')
journal = splitpub[0]
vol = splitpub[1]
issue =  splitpub[2]
doi = 'https://dx.doi.org/' + doi


blogtext = tpl.format(authors=', '.join(authorlist),
                      doi=doi,
                      title=title,
                      journal=journal,
                      vol=vol, issue=issue,
                      abstract=abstract,
                      kw=kw)
print(blogtext)
f = open('blogpost.txt', 'w')
f.write(blogtext)
f.close()
