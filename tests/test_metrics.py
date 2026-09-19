import numpy as np
import pandas as pd
import pytest

from intraday_turning_point.config import Config, Window, parse_windows
from intraday_turning_point.metrics import (
    SEGMENTS,
    daily_bars,
    event_outcomes,
    momentum,
    score_symbol,
    summarize,
    window_mask,
)


def test_hand_calculated_base_and_weight(bars):
    row = score_symbol(bars, "TEST", Config()).iloc[0]
    # mean close=104; baseline return=.02; window max return=.10; range=.12.
    assert row.base_metric == pytest.approx(2 / 3)
    assert row.gamma == 30
    # prior/future low=99, high=111: theta=50*(12/99+12/111).
    assert row.theta == pytest.approx(50 * (12 / 99 + 12 / 111))
    assert row.score == pytest.approx((2 / 3) * (30 + 50 * (12 / 99 + 12 / 111)))


@pytest.mark.parametrize("mode", ["asof_close", "retrospective"])
def test_future_information_boundary(bars, mode):
    changed = bars.copy()
    boundary = pd.Timestamp("2024-01-08")
    changed.loc[changed.datetime >= boundary, ["open", "high", "low", "close"]] *= 0.6
    original = score_symbol(bars, "TEST", Config(mode=mode))
    later = score_symbol(changed, "TEST", Config(mode=mode))
    keep = original.date < "2024-01-08"
    if mode == "asof_close":
        pd.testing.assert_frame_equal(original[keep], later[keep])
        prefix = score_symbol(bars[bars.datetime < boundary], "TEST", Config(mode=mode))
        pd.testing.assert_frame_equal(original[keep].reset_index(drop=True), prefix)
        assert (original.future_days_used == 0).all()
    else:
        assert not np.allclose(original[keep].theta, later[keep].theta)


def test_flat_zero_volume_and_small_amplitude(bars):
    flat = bars.copy()
    flat[["open", "high", "low", "close"]] = 100.0
    flat["volume"] = 0
    assert (score_symbol(flat, "TEST", Config(), include_segments=False).score == 0).all()
    assert (daily_bars(flat).vwap_proxy == 100).all()
    flat["high"] = 101.0
    assert (score_symbol(flat, "TEST", Config(), include_segments=False).score == 0.2).all()


def test_missing_window_is_not_a_negative_observation(bars):
    frame = bars[bars.datetime.dt.strftime("%H:%M") == "09:31"]
    scores = score_symbol(frame, "TEST", Config(), include_segments=False)
    assert scores.score.isna().all()
    result = summarize(scores, 8)
    assert (result.valid_days == 0).all()
    assert result.exceedance_rate.isna().all()
    assert (result.missing_window_days == 8).all()


def test_segment_boundaries_and_noon_bar(bars):
    day = bars.iloc[:8]
    masks = [window_mask(day, (w,), exclusive_start=True) for w in SEGMENTS]
    assert (np.sum(masks, axis=0) == 1).all()
    noon = day.datetime.dt.strftime("%H:%M") == "11:30"
    assert window_mask(day, Config().control)[noon].all()


def test_lunch_and_sparse_elapsed_time():
    df = pd.DataFrame(
        {"datetime": pd.to_datetime(["2024-01-02 11:30", "2024-01-02 13:01", "2024-01-02 13:11"])}
    )
    r = np.array([0.0, 0.01, 0.02])
    # No morning bar allowed in the 13:01 lookback.
    assert momentum(df, r, np.array([False, True, False]), Config(mode="asof_close")) == 1
    # 10 elapsed minutes, not one observed-row step.
    assert momentum(df, r, np.array([False, False, True]), Config(mode="asof_close")) == 10
    assert momentum(df, r, np.array([False, False, True]), Config()) == 30


def test_event_labels_use_next_open_and_keep_tail(bars):
    frame = bars.copy()
    second = frame.datetime.dt.normalize().unique()[1]
    frame.loc[frame.datetime.dt.normalize() == second, ["open", "high", "low", "close"]] *= 2
    scores = score_symbol(frame, "TEST", Config(mode="asof_close"))
    result = event_outcomes(frame, scores, horizon=2)
    first = result.iloc[0]
    assert first.entry_date == "2024-01-03"
    assert first.end_date == "2024-01-04"
    assert first.forward_return == -0.5  # 100 / 200 - 1, not same-day 100 / 100 - 1.
    assert len(result) == 8
    assert result.tail(2).forward_return.isna().all()
    assert not result.tail(2).complete_horizon.any()
    with pytest.raises(ValueError, match="require asof_close"):
        event_outcomes(frame, score_symbol(frame, "TEST", Config()))


def test_strict_event_threshold():
    scores = pd.DataFrame(
        {"symbol": ["X"] * 3, "window_set": ["primary"] * 3, "score": [8.0, 9.0, np.nan]}
    )
    row = summarize(scores, 8).iloc[0]
    assert row.exceedance_days == 1
    assert row.valid_days == 2
    assert row.exceedance_rate == 0.5
    assert row.score_sum_above_threshold == 9


@pytest.mark.parametrize(
    "value", ["10:30-10:00", "11:00-13:30", "9:30-10:00", "10:00-10:30,10:30-11:00"]
)
def test_invalid_window_config(value):
    with pytest.raises(ValueError):
        parse_windows(value)


def test_config_validation():
    with pytest.raises(ValueError):
        Config(primary=(Window("10:00", "10:45"), Window("10:15", "10:30")))
    for kwargs in [{"lookback": 0}, {"event_threshold": float("nan")}, {"context_days": True}]:
        with pytest.raises(ValueError):
            Config(**kwargs)
