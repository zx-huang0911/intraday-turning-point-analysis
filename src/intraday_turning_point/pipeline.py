"""One analysis path shared by the CLI, reports, and reproducible demo."""

import importlib.metadata
import json
import platform
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from .config import Config
from .data import inventory, load_symbol, quality, sha256
from .metrics import event_outcomes, score_symbol, summarize
from .report import build_report


def analyze(
    source: Path,
    output: Path,
    config: Config,
    *,
    symbols=None,
    skip_invalid=False,
    data_kind="user-provided",
    horizon=5,
    include_inputs=False,
):
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a new directory to preserve prior evidence")
    if source.is_dir() and (output == source or source in output.parents):
        raise ValueError("Output must be outside the input data directory")
    files = inventory(source)
    if symbols:
        missing = set(symbols) - files.keys()
        if missing:
            raise ValueError(f"Symbols not found: {', '.join(sorted(missing))}")
        files = {s: files[s] for s in sorted(set(symbols))}
    if horizon < 1:
        raise ValueError("Horizon must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        scores, outcomes, cases, checks = [], [], [], []
        sources = []
        for symbol, paths in files.items():
            for path in paths:
                sources.append(
                    {
                        "symbol": symbol,
                        "file": str(path.relative_to(source) if source.is_dir() else path.name),
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                    }
                )
            try:
                frame = load_symbol(paths)
            except ValueError as exc:
                if not skip_invalid:
                    raise ValueError(f"{symbol}: {exc}") from exc
                checks.append({"symbol": symbol, "status": "rejected", "reason": str(exc)})
                continue
            checks.append({"symbol": symbol, "status": "accepted", **quality(frame)})
            scored = score_symbol(frame, symbol, config)
            scores.append(scored)
            if config.mode == "asof_close":
                outcomes.append(event_outcomes(frame, scored, horizon))
            primary = scored[scored.window_set == "primary"].dropna(subset=["score"])
            if not primary.empty:
                selected = primary.sort_values(["score", "date"], ascending=[False, True]).iloc[0]
                day = frame[frame.datetime.dt.strftime("%Y-%m-%d") == selected.date]
                cases.append(
                    {
                        "symbol": symbol,
                        "date": selected.date,
                        "score": float(selected.score),
                        "selection": "Highest primary score in this input; illustrative, not random",
                        "time": day.datetime.dt.strftime("%H:%M").tolist(),
                        "close": day.close.tolist(),
                        "volume": day.volume.tolist(),
                    }
                )
        if not scores:
            raise ValueError("No valid symbols remain; inspect source data")
        all_scores = pd.concat(scores, ignore_index=True)
        summary = summarize(all_scores, config.event_threshold)
        all_scores.to_csv(stage / "daily_scores.csv", index=False)
        summary.to_csv(stage / "summary.csv", index=False)
        if outcomes:
            pd.concat(outcomes, ignore_index=True).to_csv(stage / "event_outcomes.csv", index=False)
        if include_inputs:
            shutil.copytree(source, stage / "synthetic_inputs")
        manifest = {
            "schema_version": 1,
            "data_kind": data_kind,
            "config": config.to_dict(),
            "event_horizon_observed_sessions": horizon if outcomes else None,
            "software": {
                p: importlib.metadata.version(p)
                for p in ["intraday-turning-point", "numpy", "pandas", "matplotlib"]
            },
            "python": platform.python_version(),
            "inputs": sources,
            "quality": checks,
            "policy": {
                "invalid_symbols": "skip" if skip_invalid else "fail",
                "missing_windows": "NaN; excluded from valid-day denominator",
                "case_selection": "Highest primary score per symbol; selected after analysis",
                "return_interpretation": "Forward labels only; no strategy or portfolio returns",
            },
        }
        build_report(stage, all_scores, summary, cases, manifest)
        manifest["outputs"] = {
            str(p.relative_to(stage)): sha256(p) for p in sorted(stage.rglob("*")) if p.is_file()
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Never replace an existing report, even if it appeared while computing.
        if output.exists():
            raise ValueError("Output appeared during analysis; refusing to replace it")
        stage.rename(output)
        return manifest
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
