"""Command-line entry point; all computation is local and offline."""

import argparse
import tempfile
from pathlib import Path

from .config import Config, parse_windows
from .demo import generate
from .pipeline import analyze


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Intraday window analysis — research, not trading advice"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate artificial data and a complete offline report")
    demo.add_argument("--out", type=Path, default=Path("output/demo"))
    demo.add_argument("--mode", choices=["retrospective", "asof_close"], default="retrospective")
    run = sub.add_parser("analyze", help="Analyze CSV files you are authorized to use")
    run.add_argument("--data", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--symbols", nargs="+", help="Filename symbols, e.g. 000554 002639")
    run.add_argument("--mode", choices=["retrospective", "asof_close"], default="retrospective")
    run.add_argument("--primary", default="10:15-10:45,13:40-14:00")
    run.add_argument("--control", default="11:00-11:30,13:00-13:20")
    run.add_argument("--lookback", type=int, default=15)
    run.add_argument("--context-days", type=int, default=5)
    run.add_argument("--base-threshold", type=float, default=0.4)
    run.add_argument("--event-threshold", type=float, default=8)
    run.add_argument("--horizon", type=int, default=5)
    run.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Explicitly reject entire invalid symbols and record why",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".synthetic-", dir=args.out.parent) as tmp:
                source = Path(tmp)
                generate(source)
                manifest = analyze(
                    source,
                    args.out,
                    Config(mode=args.mode),
                    data_kind="synthetic",
                    include_inputs=True,
                )
        else:
            config = Config(
                primary=parse_windows(args.primary),
                control=parse_windows(args.control),
                mode=args.mode,
                lookback=args.lookback,
                context_days=args.context_days,
                base_threshold=args.base_threshold,
                event_threshold=args.event_threshold,
            )
            manifest = analyze(
                args.data,
                args.out,
                config,
                symbols=args.symbols,
                skip_invalid=args.skip_invalid,
                horizon=args.horizon,
            )
        accepted = sum(q["status"] == "accepted" for q in manifest["quality"])
        rejected = len(manifest["quality"]) - accepted
        print(f"Report: {(args.out / 'index.html').resolve()}")
        print(
            f"Symbols accepted: {accepted}; rejected: {rejected}. See manifest.json for provenance."
        )
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
