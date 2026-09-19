# Intraday Turning Point Analysis

[![Python checks](https://github.com/zx-huang0911/intraday-turning-point-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/zx-huang0911/intraday-turning-point-analysis/actions/workflows/ci.yml)

A reproducible, window-based exploration of intraday turning-point hypotheses in Chinese A-share data. Originating from a behavioral finance course project, it turns minute OHLCV inputs into daily scores, window comparisons and a portable offline report.

[中文](README.md) · [Method specification](docs/methodology.md) · [Data policy](docs/data-card.md) · [Validation](docs/validation.md)

![Offline report generated with synthetic data](docs/assets/report-preview.png)

## Run locally

Python 3.11 or newer. From the repository root:

```bash
git clone https://github.com/zx-huang0911/intraday-turning-point-analysis.git
cd intraday-turning-point-analysis
python -m venv .local/venv
source .local/venv/bin/activate
python -m pip install -e .
itp demo --out output/demo
```

Open `output/demo/index.html`, or the pre-generated `examples/report/index.html`. No server, API key, external fonts or CDN is required. The synthetic generator deliberately plants peaks; it demonstrates functionality and cannot establish market effects. Choose a fresh output directory on each run.

```bash
itp analyze --data .local/data --out output/study --mode asof_close
```

Inputs require `datetime,open,high,low,close,volume`, local Asia/Shanghai minute timestamps, and one symbol per file. Filenames determine symbols. Invalid data fail by default; explicit `--skip-invalid` excludes entire invalid symbols and records why. No silent cleaning or price interpolation occurs.

## Information boundaries

| Mode | Information used | Interpretation |
| --- | --- | --- |
| `retrospective` | Current day, previous lows, **future lows** | Descriptive reconstruction of the original scoring method |
| `asof_close` | Current day and previous observed days only | Modified close-of-day features; **not** an intraday predictive model |

The latter exports forward outcome labels from the next observed session's first open to a later session's last close. Overlapping events, costs, liquidity and positions are not modeled. These labels are not strategy or portfolio returns. Incomplete input days require particular care: a last available bar is not necessarily the actual session close.

Outputs include per-day scores, valid/missing-day denominators, summary CSV, standalone SVG/PNG charts and a manifest with versions, configuration, checks and SHA-256 hashes. Illustrative cases are selected by highest primary score, not random sampling.

## Evidence and limits

Tests cover hand-calculated values, future-data perturbation, lunch breaks, incomplete windows, invalid inputs and end-to-end execution. A local audit compared eight accepted historical symbols against the supplied legacy implementation; two additional symbols were rejected for nonpositive prices. See the [validation record](docs/validation.md) for scope. No claim of independent review, statistical significance, profitability or causal identification is made.

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
```

## Attribution and license

Zixin Huang (黄子欣) led topic selection, principal implementation and visualizations in the original course project. Acknowledgments: 史一诺, 韩鎔旭 and 张钰浛; see [AUTHORS.md](AUTHORS.md).

Original software, documentation and synthetic examples: [MIT](LICENSE). Third-party market data are **not** included or relicensed. Use your own authorized inputs; see the [data card](docs/data-card.md).
