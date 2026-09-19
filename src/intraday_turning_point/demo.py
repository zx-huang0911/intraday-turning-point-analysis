"""Generate deterministic artificial OHLCV bars; never market observations."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(out: Path, days: int = 24, seed: int = 42):
    out.mkdir(parents=True, exist_ok=True)
    for name, offset in [("DEMO_A", 0), ("DEMO_B", 1)]:
        rng = np.random.default_rng(seed + offset)
        records = []
        for i, date in enumerate(pd.bdate_range("2024-01-02", periods=days)):
            # Weekday grid is artificial, not an exchange trading calendar.
            stamps = pd.date_range(
                date + pd.Timedelta(hours=9, minutes=31), periods=120, freq="min"
            ).append(
                pd.date_range(date + pd.Timedelta(hours=13, minutes=1), periods=120, freq="min")
            )
            x = np.arange(240)
            baseline = 10 + offset * 4 + 0.2 * np.sin(i / 3)
            noise = np.cumsum(rng.normal(0, 0.0012, 240))
            # Deliberately planted peaks demonstrate, but cannot validate, the hypothesis.
            peak = (
                0.08 * np.exp(-(((x - (65 if offset == 0 else 102)) / 14) ** 2))
                if i % 3 == 0
                else 0
            )
            close = baseline * (1 + noise + peak)
            op = np.r_[baseline, close[:-1]]
            high = np.maximum(op, close) + rng.uniform(0.002, 0.02, 240)
            low = np.minimum(op, close) - rng.uniform(0.002, 0.02, 240)
            volume = rng.integers(100, 10000, 240)
            records.extend(zip(stamps, op, high, low, close, volume))
        df = pd.DataFrame(records, columns=["datetime", "open", "high", "low", "close", "volume"])
        df.to_csv(out / f"{name}.csv", index=False, float_format="%.6f")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/demo-data"))
    args = parser.parse_args()
    generate(args.output)
    print(f"Synthetic samples written to {args.output}")
