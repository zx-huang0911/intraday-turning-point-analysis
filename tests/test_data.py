import pandas as pd
import pytest

from intraday_turning_point.data import inventory, load_symbol, quality, validate_frame


@pytest.mark.parametrize(
    "column,value,match",
    [
        ("close", 0, "positive"),
        ("volume", -1, "nonnegative"),
        ("high", 1, "OHLC"),
        ("close", float("inf"), "non-finite"),
        ("datetime", pd.Timestamp("2024-01-02 12:00"), "session"),
        ("datetime", pd.Timestamp("2024-01-02 09:31:00.000000001"), "minute-aligned"),
        ("datetime", pd.NaT, "Null"),
    ],
)
def test_bad_values_rejected(bars, column, value, match):
    frame = bars.copy()
    frame.loc[0, column] = value
    with pytest.raises(ValueError, match=match):
        validate_frame(frame)


def test_duplicates_missing_and_timezone(bars):
    with pytest.raises(ValueError, match="Duplicate"):
        validate_frame(pd.concat([bars, bars.iloc[:1]]))
    with pytest.raises(ValueError, match="Missing"):
        validate_frame(bars.drop(columns="volume"))
    zoned = bars.copy()
    zoned.datetime = zoned.datetime.dt.tz_localize("Asia/Shanghai")
    with pytest.raises(ValueError, match="timezone-naive"):
        validate_frame(zoned)


def test_multi_file_symbol_and_duplicate_year_detection(bars, tmp_path):
    bars.iloc[:32].to_csv(tmp_path / "000001_2020.csv", index=False)
    bars.iloc[32:].to_csv(tmp_path / "000001_2021.csv", index=False)
    paths = inventory(tmp_path)["000001"]
    pd.testing.assert_frame_equal(load_symbol(paths), bars)
    bars.to_csv(tmp_path / "000001_duplicate.csv", index=False)
    with pytest.raises(ValueError, match="Duplicate"):
        load_symbol(inventory(tmp_path)["000001"])


def test_sorting_and_completeness_diagnostic(bars):
    pd.testing.assert_frame_equal(validate_frame(bars.iloc[::-1]), bars)
    assert quality(bars)["days_not_240_bars"] == 8
