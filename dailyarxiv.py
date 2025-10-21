import argparse
import numpy as np
import arxivposts
import paperpatrol


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Check arXiv for group papers.")
    parser.add_argument("-d", "--date", help="Specific date in dd/mm/yy format", default="today")
    parser.add_argument("-s", "--since", help="Catch-up since date in dd/mm/yy format")
    parser.add_argument("-i", "--identifier", help="Specific arXiv ID, e.g. 2108.11780")
    parser.add_argument("-p", "--place", default="birmingham", help="Institution key (default: birmingham)")
    return parser.parse_args()

def run_paperpatrol(place, date, since=None, identifier=None):
    """Run paperpatrol with the given options."""
    print(f"\nChecking arXiv for {place.capitalize()} (Date: {date}, Since: {since or 'N/A'})")

    return paperpatrol.main(
        workplaceidstr=place,
        template=paperpatrol.dailyTemplate(),
        options=dict(date=date, since=since, identifier=identifier),
    )

def add_isimbablogposts(non_issues):
    if not non_issues:
        print("\nNo papers today.")
        return

    print("\nScience! Print the papers and show the world!")
    try:
        isimba_group = np.loadtxt("isimbagroup.txt", dtype=str)
    except Exception as e:
        print(f"Could not read isimabagroup.txt: {e}")
        return

    for pid, author in non_issues:
        for name in author.replace(",", "").split():
            if name in isimba_group:
                print(f"{author} is in paper {pid}")
                arxivposts.main(pid)

def main():
    args = parse_arguments()
    non_issues = run_paperpatrol(
        place=args.place.lower(),
        date=args.date,
        since=args.since,
        identifier=args.identifier,
    )

    if args.place.lower() == "sac":
        add_isimbablogposts(non_issues)
    else:
        print(f"\nDone for {args.place.capitalize()} — {len(non_issues)} papers found.")


if __name__ == "__main__":
    main()
