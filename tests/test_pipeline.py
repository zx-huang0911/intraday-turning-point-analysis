import json
import subprocess
import sys

import pandas as pd
import pytest

from intraday_turning_point.config import Config
from intraday_turning_point.data import sha256
from intraday_turning_point.pipeline import analyze


def test_end_to_end_provenance_and_no_overwrite(bars, tmp_path):
    source = tmp_path / "TEST.csv"
    bars.to_csv(source, index=False)
    output = tmp_path / "report"
    manifest = analyze(source, output, Config(mode="asof_close"))
    assert manifest["inputs"][0]["sha256"] == sha256(source)
    assert manifest["quality"][0]["rows"] == len(bars)
    assert manifest["data_kind"] == "user-provided"
    assert "synthetic_inputs" not in [p.name for p in output.iterdir()]
    assert json.loads((output / "manifest.json").read_text())["config"]["mode"] == "asof_close"
    for name, digest in manifest["outputs"].items():
        assert sha256(output / name) == digest
    scores = pd.read_csv(output / "daily_scores.csv")
    assert len(scores) == 8 * 10
    assert (scores.future_days_used == 0).all()
    original = (output / "index.html").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        analyze(source, output, Config())
    assert (output / "index.html").read_bytes() == original


def test_rejected_symbols_are_explicit_and_default_fails(bars, tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    bars.to_csv(source / "GOOD.csv", index=False)
    bad = bars.copy()
    bad.loc[0, "close"] = 0
    bad.to_csv(source / "BAD.csv", index=False)
    with pytest.raises(ValueError, match="positive"):
        analyze(source, tmp_path / "failed", Config())
    assert not (tmp_path / "failed").exists()
    result = analyze(source, tmp_path / "partial", Config(), skip_invalid=True)
    assert len(result["inputs"]) == 2
    assert [q["symbol"] for q in result["quality"] if q["status"] == "rejected"] == ["BAD"]
    with pytest.raises(ValueError, match="outside"):
        analyze(source, source / "results", Config())


def test_installed_cli_demo(tmp_path):
    output = tmp_path / "demo"
    result = subprocess.run(
        [sys.executable, "-m", "intraday_turning_point.cli", "demo", "--out", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["data_kind"] == "synthetic"
    assert len(list((output / "synthetic_inputs").glob("*.csv"))) == 2
    html = (output / "index.html").read_text()
    assert "__REPORT_DATA__" not in html
    assert "https://" not in html  # Report has no remote asset requirements.
    assert not (output / "event_outcomes.csv").exists()


def test_report_handles_no_primary_observations(bars, tmp_path):
    source = tmp_path / "EARLY.csv"
    early = bars[bars.datetime.dt.strftime("%H:%M") == "09:31"]
    early.to_csv(source, index=False)
    out = tmp_path / "report"
    analyze(source, out, Config())
    assert (out / "index.html").is_file()
    assert not (out / "selected_case.svg").exists()
    result = pd.read_csv(out / "summary.csv")
    assert result[result.window_set == "primary"].valid_days.iloc[0] == 0
