"""Compare user-supplied, trusted legacy code against the current retrospective core.

The original code and market data are not bundled. Loading --legacy-metrics
executes that Python file: only use a trusted local copy. No network is used.
"""

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

from intraday_turning_point.config import Config
from intraday_turning_point.data import inventory, load_symbol, quality, sha256
from intraday_turning_point.metrics import score_symbol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-metrics", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output already exists; use a new evidence filename")
    spec = importlib.util.spec_from_file_location("legacy_metrics", args.legacy_metrics)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    config = Config(lookback=10)
    records = []
    for symbol, paths in inventory(args.data).items():
        record = {
            "symbol": symbol,
            "inputs": [{"file": p.name, "sha256": sha256(p)} for p in paths],
        }
        try:
            frame = load_symbol(paths)
        except ValueError as exc:
            record.update(status="rejected", reason=str(exc))
            records.append(record)
            continue
        modern = score_symbol(frame, symbol, config, include_segments=False)
        errors = []
        for group, windows in [("primary", config.primary), ("control", config.control)]:
            old = legacy.compute_daily_detailed_metrics(
                frame,
                [(w.start, w.end) for w in windows],
                base_threshold=0.4,
                lookback_minutes=10,
                lookback_days=5,
            )
            new = modern[modern.window_set == group]
            if list(pd.to_datetime(old.index).strftime("%Y-%m-%d")) != list(new.date):
                raise ValueError(f"{symbol}: date alignment differs")
            before, after = old.final_metric.to_numpy(), new.score.to_numpy()
            # Missing-window semantics deliberately differ; baseline samples have none.
            if not np.isfinite(before).all() or not np.isfinite(after).all():
                raise ValueError(
                    f"{symbol}: non-finite score; this comparison requires complete windows"
                )
            errors.append(float(np.max(np.abs(before - after))))
        record.update(
            status="accepted", **quality(frame), legacy_max_absolute_score_difference=max(errors)
        )
        records.append(record)
    payload = {
        "config": config.to_dict(),
        "legacy_metrics_sha256": sha256(args.legacy_metrics),
        "comparison": "primary/control daily scores; no half-hour segments or backtests",
        "records": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    accepted = [r for r in records if r["status"] == "accepted"]
    if not accepted or any(r["legacy_max_absolute_score_difference"] > 1e-10 for r in accepted):
        raise SystemExit("Legacy comparison failed; inspect evidence")
    print(f"Compared {len(accepted)} symbols; rejected {len(records) - len(accepted)}")


if __name__ == "__main__":
    main()
