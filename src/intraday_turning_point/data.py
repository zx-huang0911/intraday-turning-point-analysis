"""Validated CSV input. Never fetch data or credentials implicitly."""

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Input contains no bars")
    df = frame[COLUMNS].copy()
    try:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="raise")
        if df["datetime"].dt.tz is not None:
            raise ValueError("Use timezone-naive Asia/Shanghai local timestamps")
        for name in COLUMNS[1:]:
            df[name] = pd.to_numeric(df[name], errors="raise").astype("float64")
    except (TypeError, AttributeError) as exc:
        raise ValueError("Invalid timestamp or numeric column") from exc
    if df["datetime"].isna().any() or not np.isfinite(df[COLUMNS[1:]].to_numpy()).all():
        raise ValueError("Null or non-finite values are not allowed")
    if df["datetime"].duplicated().any():
        raise ValueError("Duplicate timestamps: one symbol and one bar per timestamp are required")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Prices must be positive")
    if (df["volume"] < 0).any():
        raise ValueError("Volume must be nonnegative")
    if (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    ).any():
        raise ValueError("OHLC range is inconsistent")
    t = df["datetime"].dt.strftime("%H:%M:%S")
    valid = t.between("09:30:00", "11:30:00") | t.between("13:00:00", "15:00:00")
    if not valid.all() or (df["datetime"] != df["datetime"].dt.floor("min")).any():
        raise ValueError("Expected minute-aligned daytime session bars")
    return df.sort_values("datetime").reset_index(drop=True)


def symbol_for(path: Path) -> str:
    match = re.match(r"^(\d{6})(?:[_.-]|$)", path.stem)
    symbol = match.group(1) if match else path.stem
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", symbol):
        raise ValueError(f"Use a simple symbol filename: {path.name}")
    return symbol


def inventory(source: Path) -> dict[str, list[Path]]:
    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = sorted(source.rglob("*.csv"))
    else:
        raise ValueError(f"Input does not exist: {source}")
    if not files:
        raise ValueError("No CSV files found")
    result: dict[str, list[Path]] = {}
    for path in files:
        result.setdefault(symbol_for(path), []).append(path)
    return result


def load_symbol(paths: list[Path]) -> pd.DataFrame:
    return validate_frame(pd.concat([pd.read_csv(p) for p in paths], ignore_index=True))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quality(frame: pd.DataFrame) -> dict:
    dates = frame["datetime"].dt.normalize()
    counts = frame.groupby(dates).size()
    return {
        "rows": len(frame),
        "days": len(counts),
        "first": str(frame["datetime"].min()),
        "last": str(frame["datetime"].max()),
        "min_bars_per_day": int(counts.min()),
        "max_bars_per_day": int(counts.max()),
        "days_not_240_bars": int((counts != 240).sum()),
        "zero_volume_bars": int((frame["volume"] == 0).sum()),
        "note": "240 is a diagnostic reference, not a completeness guarantee; calendar not inferred.",
    }
