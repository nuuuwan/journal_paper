import argparse

from jp import JournalPaper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a journal paper")
    parser.add_argument(
        "dir_path", help="Path to the paper directory", required=True
    )
    args = parser.parse_args()

    paper = JournalPaper(args.dir_path)
    paper.build()
