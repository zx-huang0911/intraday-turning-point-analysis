import pandas as pd
import pytest

from intraday_turning_point.data import validate_frame


@pytest.fixture
def bars():
    # Small, intentionally incomplete days with hand-checkable values.
    rows = []
    for date in pd.bdate_range("2024-01-02", periods=8):
        for clock, op, hi, low, close in [
            ("09:31", 100, 101, 99, 100),
            ("10:15", 100, 111, 100, 110),
            ("10:45", 110, 110, 104, 105),
            ("11:30", 105, 106, 104, 105),
            ("13:01", 105, 106, 102, 103),
            ("13:40", 103, 108, 103, 107),
            ("14:00", 107, 108, 101, 102),
            ("15:00", 102, 103, 99, 100),
        ]:
            rows.append([f"{date:%Y-%m-%d} {clock}:00", op, hi, low, close, 1])
    return validate_frame(
        pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    )
