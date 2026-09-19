# Intraday Turning Point Analysis

[![Python checks](https://github.com/zx-huang0911/intraday-turning-point-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/zx-huang0911/intraday-turning-point-analysis/actions/workflows/ci.yml)

A 股分时转折点分析，行为金融课程项目。

[研究报告 PDF](docs/reports/intraday-turning-point-report.pdf) · [English](README.en.md) · [方法说明](docs/methodology.md) · [数据说明](docs/data-card.md)

## 项目介绍

这个项目研究 A 股在特定时段出现的拉升与回落现象，主要关注上午 10:30 附近和下午 14:00 前的价格走势。我们用分钟行情比较这些时段与其他时段的差异，再结合前后几个交易日的走势查看具体案例。我在小组中负责选题、主要代码和数据可视化，其他成员的分工见 [AUTHORS.md](AUTHORS.md)。

分析时先固定时间窗口，计算窗口内最高收盘涨幅相对全日基线的偏离，再按当日振幅归一化。短时上涨速度和前后日线位置分别用 gamma、theta 两个权重表示。程序按股票和日期批量计算，输出窗口对比、逐日明细和案例图。

![报告图 1：分时转折点案例示意图](docs/assets/course/report-figure-1.png)

*图 1：研究报告第 4 页的案例示意图，直接提取自 PDF。图中为两面针（600249）2025-09-10 的行情截图及标注，用于说明研究关注的形态，与下方的 2020 年计算样本不同。*

## 窗口设置与样本结果

| 组别 | 上午窗口 | 下午窗口 |
| --- | --- | --- |
| 主试验组 | 10:15–10:45 | 13:40–14:00 |
| 对照组 | 11:00–11:30 | 13:00–13:20 |

下表转录自研究报告第 10 页表 1，保留原报告的逐行数值，证券代码补齐为六位。这是历史实验记录，并非当前版本重新运行的结果。

| 股票代码 | 主试验组得分 | 对照组得分 | 差值（原报告） |
| --- | ---: | ---: | ---: |
| 000554 | 111.53 | 47.23 | 64.31 |
| 002639 | 121.83 | 100.54 | 21.30 |
| 002641 | 124.66 | 63.71 | 60.95 |
| 002642 | 104.57 | 38.90 | 65.67 |
| 002643 | 168.12 | 111.41 | 56.71 |
| 002644 | 135.37 | 62.40 | 72.97 |
| 002645 | 164.23 | 154.13 | 10.10 |
| 002646 | 235.61 | 138.60 | 97.01 |
| 002647 | 129.72 | 121.69 | 8.03 |
| 002648 | 119.16 | 75.13 | 44.04 |

报告中的汇总均值与这十行数据不一致，因此这里没有沿用均值结论；具体核对见[报告与代码的差异说明](docs/reports/README.md)。

## 典型案例

下面两张图来自原项目 `v3.0` 的 `fast_test/typical_cases` 输出，均为 **000554，2020-04-08**，保留原始图片。

![000554：2020-04-08 分时价格与成交量](docs/assets/course/000554_2020-04-08_intraday.png)

*分时图：上半部分为分钟收盘价，下半部分为成交量；阴影标出两个主试验窗口。*

![000554：典型案例日前后的日 K 线与成交量](docs/assets/course/000554_2020-04-08_kline.png)

*日 K 线图：蓝色虚线标记案例日，展示 2020-03-31 至 2020-04-15 的走势。结合前后日线查看，是原方法引入 theta 权重的出发点。*

对应的指标取自原目录的 `typical_cases_list.csv`，下表保留四位小数：

| 股票代码 | 日期 | 基础窗口指标 | gamma | theta | 加权得分 |
| --- | --- | ---: | ---: | ---: | ---: |
| 000554 | 2020-04-08 | 0.5240 | 30.0000 | 23.8462 | 28.2127 |

案例是按高分筛选出来的，适合解释指标含义，不能代表所有交易日。原方法中的 theta 使用未来几日低点，因此这些图和得分用于回顾分析。

## 运行代码

需要 Python 3.11 或更新版本：

```bash
git clone https://github.com/zx-huang0911/intraday-turning-point-analysis.git
cd intraday-turning-point-analysis
python -m venv .local/venv
source .local/venv/bin/activate
python -m pip install -e .
itp demo --out output/demo
```

用浏览器打开 `output/demo/index.html` 可以查看结果。演示使用合成数据，方便在没有行情文件时运行；上面的历史案例图不来自这组演示数据。仓库也保留了预生成的 [HTML 示例](examples/report/index.html)，下载后可直接打开。

分析自己的 CSV：

```bash
itp analyze --data .local/data --out output/my-study --mode retrospective
```

输入需要 `datetime,open,high,low,close,volume` 六列，文件名如 `000001_2020.csv`。字段、时间戳和数据获取说明见[数据说明](docs/data-card.md)。输出目录需使用新名称，避免覆盖已有结果。异常数据默认报错；加上 `--skip-invalid` 才会跳过整个异常标的，并记录原因。

| 模式 | 计算方式 |
| --- | --- |
| `retrospective` | 沿用原项目的回顾评分，theta 包含未来低点 |
| `asof_close` | 使用当日和此前数据，另导出从下一观测日开盘起算的收益标签 |

`asof_close` 是整理代码时增加的分析模式，仍需完整的当日行情；收益标签没有模拟仓位、交易费用或实际成交。完整公式见[方法说明](docs/methodology.md)。

## 输出文件

| 文件 | 内容 |
| --- | --- |
| `daily_scores.csv` | 每个标的、日期和窗口组的基础值、权重、得分 |
| `summary.csv` | 有效日、缺失日、超阈值日数及分数汇总 |
| `event_outcomes.csv` | 收盘时点模式的前瞻收益标签 |
| `index.html` | 窗口对比、案例曲线和逐日得分 |
| `window_comparison.*` / `selected_case.*` | SVG、PNG 图表 |
| `manifest.json` | 本次参数、软件版本、数据检查结果与文件哈希 |

## 测试与版本说明

当前代码由课程项目整理而来，增加了 CSV 校验、测试和安装入口。Python 3.11 / 3.12 的 CI 包括测试、格式检查、构建和演示生成；历史数据对照见[验证记录](docs/validation.md)。

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
```

[研究报告](docs/reports/intraday-turning-point-report.pdf)按原件存档，保留当时的方法和讨论。报告与当前代码在参数、缺失数据处理和策略实验上有所不同，见[差异说明](docs/reports/README.md)。后续研究仍需等时长对照和独立时间样本；这里展示的得分比较不等同于统计显著性或交易收益。

## 作者与许可

Zixin Huang（黄子欣）。感谢史一诺、韩鎔旭、张钰浛在课程项目中的协作。

代码、项目说明和合成样例采用 [MIT](LICENSE)。研究报告和历史图表作为课程材料单独存档，其中的第三方行情与软件截图不随代码重新授权。仓库不提供原始行情数据集，详见[数据说明](docs/data-card.md)。
