import argparse
import os
import schedule
import time
import numpy as np

import sac as arxiv_on_deck
import arxivposts


parser = argparse.ArgumentParser()
parser.add_argument("--date")


def main(date=None,):
    if date is None:
        date = 'today'

    print('Checks arxiv')
    # run arxiv_on_deck for sac
    non_issues = arxiv_on_deck.main(
        template=arxiv_on_deck.SACTemplate(),
        options=dict(
            #date=date,
            since='01/06/2020'
        ),
    )
    if len(non_issues) == 0:
        print('\nNo papers today')
    else:
        print('\nScience! Print the papers and show the world!')
        isimbagroup = np.loadtxt('isimbagroup.txt', dtype='str')
        for pid, author in non_issues:
            print(author)
            if author.split()[-1] in isimbagroup:
                print('%s is in paper %s' % (author, pid))
                arxivposts.main(pid)

if __name__ == "__main__":
    main(**vars(parser.parse_args()))
