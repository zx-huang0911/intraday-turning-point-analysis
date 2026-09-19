"""Auditable window scores with separate retrospective and as-of-close contexts."""

import numpy as np
import pandas as pd

from .config import Config, Window

SEGMENTS = tuple(
    Window(a, b)
    for a, b in [
        ("09:30", "10:00"),
        ("10:00", "10:30"),
        ("10:30", "11:00"),
        ("11:00", "11:30"),
        ("13:00", "13:30"),
        ("13:30", "14:00"),
        ("14:00", "14:30"),
        ("14:30", "15:00"),
    ]
)


def daily_bars(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.assign(date=frame["datetime"].dt.normalize())
    daily = df.groupby("date", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        bars=("close", "size"),
        mean_close=("close", "mean"),
    )
    weighted = (df["close"] * df["volume"]).groupby(df["date"]).sum()
    # This is a bar-close volume-weighted proxy, NOT exchange turnover VWAP.
    daily["vwap_proxy"] = (weighted / daily["volume"].replace(0, np.nan)).fillna(
        daily["mean_close"]
    )
    daily["amplitude"] = (daily["high"] - daily["low"]) / daily["open"]
    return daily


def context_weights(daily: pd.DataFrame, config: Config) -> np.ndarray:
    low, high = daily["low"].to_numpy(), daily["high"].to_numpy()
    weights = np.empty(len(daily))
    k = config.context_days
    for i in range(len(daily)):
        prior_low = low[max(0, i - k) : i].min() if i else low[i]
        rise = (high[i] - prior_low) / prior_low
        if config.mode == "retrospective":
            following = low[i + 1 : i + 1 + k]
            next_low = following.min() if len(following) else low[i]
            fall = (high[i] - next_low) / high[i]
            raw = min(rise + fall, 3 * fall)
        else:
            raw = rise
        weights[i] = np.clip(50 * raw, 2, 30)
    return weights


def window_mask(day: pd.DataFrame, windows: tuple[Window, ...], *, exclusive_start=False):
    times = day["datetime"].dt.strftime("%H:%M").to_numpy()
    mask = np.zeros(len(day), dtype=bool)
    for w in windows:
        mask |= ((times > w.start) if exclusive_start else (times >= w.start)) & (times <= w.end)
    return mask


def momentum(day: pd.DataFrame, returns: np.ndarray, mask: np.ndarray, config: Config) -> float:
    speeds = []
    times = day["datetime"].to_numpy(dtype="datetime64[m]").astype("int64")
    afternoon = (day["datetime"].dt.hour >= 13).to_numpy()
    for i in np.flatnonzero(mask):
        if i == 0:
            continue
        if config.mode == "retrospective":
            start = max(0, i - config.lookback)
            speed = (returns[i] - returns[start:i].min()) / (i - start)
        else:
            # Real elapsed minutes, no crossing lunch and no future rows.
            start = int(np.searchsorted(times, times[i] - config.lookback))
            candidates = np.arange(start, i)
            candidates = candidates[afternoon[candidates] == afternoon[i]]
            if not len(candidates):
                continue
            elapsed = times[i] - times[candidates[0]]
            speed = (returns[i] - returns[candidates].min()) / elapsed
        speeds.append(speed)
    if not speeds:
        return 1.0
    value = min(10000 * max(speeds), 30)
    return float(max(0, value) if config.mode == "asof_close" else value)


def score_symbol(frame: pd.DataFrame, symbol: str, config: Config, *, include_segments=True):
    daily = daily_bars(frame)
    theta = context_weights(daily, config)
    groups = [("primary", config.primary, False), ("control", config.control, False)]
    if include_segments:
        groups += [(f"segment:{w.label}", (w,), True) for w in SEGMENTS]
    records = []
    for day_index, (date, day) in enumerate(
        frame.groupby(frame["datetime"].dt.normalize(), sort=True)
    ):
        day = day.reset_index(drop=True)
        stats = daily.loc[date]
        returns = (day["close"].to_numpy() - stats["open"]) / stats["open"]
        baseline = ((stats["close"] + stats["vwap_proxy"]) / 2 - stats["open"]) / stats["open"]
        amplitude = stats["amplitude"]
        for group, windows, exclusive in groups:
            mask = window_mask(day, windows, exclusive_start=exclusive)
            if not mask.any():
                base, gamma = np.nan, np.nan
            else:
                base = (
                    0.0
                    if amplitude == 0
                    else 0.2
                    if amplitude < 0.04
                    else (returns[mask].max() - baseline) / amplitude
                )
                gamma = momentum(day, returns, mask, config)
            score = base * (gamma + theta[day_index]) if base > config.base_threshold else base
            records.append(
                {
                    "symbol": symbol,
                    "date": date.strftime("%Y-%m-%d"),
                    "window_set": group,
                    "base_metric": float(base),
                    "gamma": float(gamma),
                    "theta": float(theta[day_index]),
                    "score": float(score),
                    "exceedance": bool(score > config.event_threshold),
                    "amplitude": float(amplitude),
                    "window_bars": int(mask.sum()),
                    "day_bars": len(day),
                    "prior_days": min(day_index, config.context_days),
                    "future_days_used": min(len(daily) - day_index - 1, config.context_days)
                    if config.mode == "retrospective"
                    else 0,
                    "mode": config.mode,
                }
            )
    return pd.DataFrame.from_records(records)


def summarize(scores: pd.DataFrame, threshold: float) -> pd.DataFrame:
    records = []
    for (symbol, group), rows in scores.groupby(["symbol", "window_set"], sort=True):
        valid = rows["score"].dropna()
        exceeds = valid[valid > threshold]
        records.append(
            {
                "symbol": symbol,
                "window_set": group,
                "valid_days": len(valid),
                "missing_window_days": int(rows["score"].isna().sum()),
                "exceedance_days": len(exceeds),
                "exceedance_rate": len(exceeds) / len(valid) if len(valid) else np.nan,
                "score_sum_above_threshold": float(exceeds.sum()),
                "mean_score": float(valid.mean()) if len(valid) else np.nan,
            }
        )
    return pd.DataFrame.from_records(records)


def event_outcomes(frame: pd.DataFrame, scores: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """Next-observed-session open to horizon close, for ALL as-of-close days.

    Outcome labels are future information. Events can overlap. No trade execution,
    portfolio, fees, borrowing or liquidity assumptions are modeled.
    """
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be positive")
    if set(scores["mode"]) != {"asof_close"}:
        raise ValueError(
            "Event outcomes require asof_close scores; retrospective weights use future data"
        )
    daily = daily_bars(frame)
    records = []
    for _, row in scores[scores["window_set"] == "primary"].iterrows():
        i = daily.index.get_loc(pd.Timestamp(row["date"]))
        complete = i + horizon < len(daily)
        valid_score = pd.notna(row["score"])
        records.append(
            {
                "symbol": row["symbol"],
                "signal_date": row["date"],
                "score": row["score"],
                "selected": bool(row["exceedance"]),
                "valid_score": valid_score,
                "horizon_observed_sessions": horizon,
                "entry_date": daily.index[i + 1].strftime("%Y-%m-%d")
                if i + 1 < len(daily)
                else None,
                "end_date": daily.index[i + horizon].strftime("%Y-%m-%d") if complete else None,
                "forward_return": float(
                    daily.iloc[i + horizon]["close"] / daily.iloc[i + 1]["open"] - 1
                )
                if complete
                else np.nan,
                "complete_horizon": complete,
            }
        )
    return pd.DataFrame.from_records(records)
