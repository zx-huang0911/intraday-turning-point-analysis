"""Generate offline, artificial input files without running the analysis."""

import argparse
from pathlib import Path

from intraday_turning_point.demo import generate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/demo-data"))
    args = parser.parse_args()
    generate(args.output)
    print(f"Synthetic samples written to {args.output}")
