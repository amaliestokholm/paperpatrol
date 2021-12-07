import argparse
import os
import time
import numpy as np

import sac as arxiv_on_deck
import asterochronometry as arxiv_on_deck2
import arxivposts


parser = argparse.ArgumentParser()
parser.add_argument("--date")  # dd/mm/yy
parser.add_argument("--since")  # dd/mm/yy
parser.add_argument("--identifier")  # E.g. 2108.11780


def main():
    args = parser.parse_args()
    if args.date is None:
        date = 'today'
    else:
        date = args.date

    print('Checks arxiv')
    # run arxiv_on_deck for sac
    non_issues = arxiv_on_deck.main(
        template=arxiv_on_deck.SACTemplate(),
        options=dict(
            date=date,
            since=args.since,
            identifier=args.identifier
        ),
    )
    if len(non_issues) == 0:
        print('\nNo papers today')
    else:
        print('\nScience! Print the papers and show the world!')
        isimbagroup = np.loadtxt('isimbagroup.txt', dtype='str')
        for pid, author in non_issues:
            for a in author.split():
                a = a.replace(',','')
                print(a)
                if a in isimbagroup:
                    print('%s is in paper %s' % (author, pid))
                    arxivposts.main(pid)
    print('Checks arxiv')
    # run arxiv_on_deck for asterochronometry group
    non_issues = arxiv_on_deck2.main(
        template=arxiv_on_deck2.asteroTemplate(),
        options=dict(
            date=date,
            since=args.since,
            identifier=args.identifier
        ),
    )

if __name__ == "__main__":
    main()
