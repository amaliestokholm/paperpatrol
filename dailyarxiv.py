import argparse
import os
import time
import numpy as np

import arxivposts
import arxiv_on_deck


parser = argparse.ArgumentParser()
parser.add_argument(
    "-d",
    "--date",
    help="Add a specific date to the output in the dd/mm/yy format",
)
parser.add_argument(
    "-s", "--since", help="Catch-up since a specific date in dd/mm/yy format"
)
parser.add_argument(
    "-i", "--identifier", help="Request a specific arXiv ID, e.g. 2108.11780"
)


def main(place="birmingham"):
    args = parser.parse_args()
    if args.date is None:
        date = "today"
    else:
        date = args.date

    print("Checks arxiv")
    print(f"For date {date}")
    if place == "birmingham":
        # run arxiv_on_deck for asterochronometry group
        non_issues = arxiv_on_deck.main(
            workplaceidstr=place,
            template=arxiv_on_deck.dailyTemplate(),
            options=dict(date=date, since=args.since, identifier=args.identifier),
        )
    if place == "sac":
        non_issues = arxiv_on_deck.main(
            workplaceidstr=place,
            template=arxiv_on_deck.dailyTemplate(),
            options=dict(date=date, since=args.since, identifier=args.identifier),
        )
        if len(non_issues) == 0:
            print("\nNo papers today")
        else:
            print("\nScience! Print the papers and show the world!")
            isimbagroup = np.loadtxt("isimbagroup.txt", dtype="str")
            for pid, author in non_issues:
                for a in author.split():
                    a = a.replace(",", "")
                    print(a)
                    if a in isimbagroup:
                        print("%s is in paper %s" % (author, pid))
                        arxivposts.main(pid)
    if place == "asterochronometry":
        # run arxiv_on_deck for asterochronometry group
        non_issues = arxiv_on_deck.main(
            workplaceidstr=place,
            template=arxiv_on_deck.dailyTemplate(),
            options=dict(date=date, since=args.since, identifier=args.identifier),
        )


if __name__ == "__main__":
    main()
