"""Portable report and publication-ready plots; no remote services or assets."""

import json
from importlib.resources import files

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _records(frame):
    # pandas serializes NaN to JSON null, which browsers can parse consistently.
    return json.loads(frame.to_json(orient="records", double_precision=10))


def build_report(out, scores, summary, cases, manifest):
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#233b4d",
            "text.color": "#233b4d",
            "svg.hashsalt": "intraday-turning-point",
        }
    )
    primary = summary[summary.window_set == "primary"].set_index("symbol")
    control = summary[summary.window_set == "control"].set_index("symbol").reindex(primary.index)
    label = "SYNTHETIC DEMO" if manifest["data_kind"] == "synthetic" else "USER-PROVIDED DATA"
    x = np.arange(len(primary))
    fig, ax = plt.subplots(figsize=(max(7.5, len(x) * 0.6), 4.2), layout="constrained")
    ax.bar(
        x - 0.17,
        primary.exceedance_rate * 100,
        width=0.32,
        color="#147d79",
        label="Primary windows",
    )
    ax.bar(
        x + 0.17,
        control.exceedance_rate * 100,
        width=0.32,
        color="#e5ad66",
        label="Control windows",
    )
    ax.set(
        xticks=x,
        xticklabels=primary.index,
        ylabel="Days above score threshold (%)",
        title=f"Window comparison  /  {label}\n{manifest['config']['mode']} · threshold > {manifest['config']['event_threshold']:g}",
    )
    ax.legend(frameon=False)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.15)
    for ext in ["svg", "png"]:
        fig.savefig(
            out / f"window_comparison.{ext}",
            dpi=160,
            metadata={"Date": None} if ext == "svg" else {},
        )
    plt.close(fig)
    if cases:
        case = cases[0]
        fig, (ax, vol) = plt.subplots(
            2,
            1,
            figsize=(9, 5),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
            layout="constrained",
        )
        xx = np.arange(len(case["time"]))
        ax.plot(xx, case["close"], color="#147d79", linewidth=1.6)
        vol.bar(xx, case["volume"], width=1, color="#a9cbc7")
        for windows, color in [
            (manifest["config"]["primary"], "#147d79"),
            (manifest["config"]["control"], "#e5ad66"),
        ]:
            for w in windows:
                inside = [i for i, t in enumerate(case["time"]) if w["start"] <= t <= w["end"]]
                if inside:
                    ax.axvspan(inside[0] - 0.5, inside[-1] + 0.5, color=color, alpha=0.13)
        ticks = sorted(set([0, len(xx) - 1] + list(range(29, len(xx), 30))))
        vol.set(
            xticks=ticks,
            xticklabels=[case["time"][i] for i in ticks],
            ylabel="Volume",
            xlabel="Observed bars · lunch break compressed; missing bars not interpolated",
        )
        ax.set(
            ylabel="Bar close",
            title=f"{case['symbol']} · {case['date']}  /  {label}\nHighest primary-score day; illustrative selection",
        )
        ax.grid(alpha=0.15)
        for ext in ["svg", "png"]:
            fig.savefig(
                out / f"selected_case.{ext}",
                dpi=160,
                metadata={"Date": None} if ext == "svg" else {},
            )
        plt.close(fig)
    payload = {
        "manifest": manifest,
        "summary": _records(summary),
        "scores": _records(scores[scores.window_set.isin(["primary", "control"])]),
        "cases": cases,
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        .replace("<", "\\u003c")
        .replace("&", "\\u0026")
    )
    template = (
        files("intraday_turning_point")
        .joinpath("templates/report.html")
        .read_text(encoding="utf-8")
    )
    (out / "index.html").write_text(template.replace("__REPORT_DATA__", encoded), encoding="utf-8")
