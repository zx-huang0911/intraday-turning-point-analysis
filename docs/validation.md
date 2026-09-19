# 验证记录

本记录对应 2026-09-19 的本地发布候选版本。区分软件正确性检查、历史算法一致性与研究有效性；前两者通过不代表第三者已得到证明。

## 软件检查

- **28 项自动测试通过**：手算公式、未来行情扰动、截断输入一致性、平盘与零成交量、缺失窗口、午休和稀疏分钟、分段端点、事件标签起止、尾部缺失、坏 OHLC、非分钟时间、时区、重复文件、输出保护及 CLI。
- Ruff 静态检查与格式检查通过。
- 构建 sdist 与 wheel；在第二个独立环境按带哈希的依赖快照安装，再安装 wheel 并执行测试和 `asof_close` 合成演示。报告模板随 wheel 打包。
- Chromium 桌面 1440×1100、手机 390×844 检查通过：标签切换、标的选择、悬停价格、质量表、键盘切换、可见下载目标、页面无横向溢出；没有 JavaScript 异常或外部资源请求。见[浏览器记录](evidence/browser-check.json)。
- GitHub Actions 已在 **Python 3.11 / 3.12、Ubuntu** 上通过测试、Ruff 检查、安装包构建与演示生成；[首次公开版本的运行记录](https://github.com/zx-huang0911/intraday-turning-point-analysis/actions/runs/35421923152) 对应代码提交 `d2ec998`。本地实际验证环境为 **Python 3.12.12 / Linux**，后续状态以仓库 Actions 为准。

环境：NumPy 2.5.3、pandas 2.3.3、Matplotlib 3.11.2、pytest 9.1.1、Ruff 0.16.8；完整依赖见 `requirements-dev.lock`。浏览器仅用于开发验证，运行项目无需 Playwright。

```bash
# Python 3.12 的依赖快照复现
python -m venv .local/venv
source .local/venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
pytest
ruff check src tests scripts
ruff format --check src tests scripts
itp demo --out output/reproduced
```

## 真实行情与旧实现一致性

只读取作者提供的旧项目 `data/fast_test`，未复制或修改行情原件。共 10 个 CSV，各 58,320 行；通过严格检查的 8 个标的共 **466,560 条分钟记录、1,944 个标的日**，均为 2020-01-02 至 2020-12-31 的 243 个观测日。

| 结果 | 标的 |
| --- | --- |
| 通过检查并参与对照 | 000554、002639、002641、002643、002644、002646、002647、002648 |
| 非正价格，拒绝整标的 | 002642、002645；本地检查各有 1 条非正价格记录 |

使用 `compute_daily_detailed_metrics` 与新版 `retrospective` 对照：基础阈值 0.4、回看 10 行、前后 5 个观测日，比较两个窗口组的全部逐日得分。最大绝对差异为 **1.1724 × 10⁻¹³**，处于浮点舍入量级。输入与原算法文件的 SHA-256、逐标的质量和误差见[机器可读记录](evidence/legacy-comparison.json)。

两种模式也都完成了上述真实数据的完整 CLI 流程，均记录 8 个接受标的和 2 个排除标的；真实报告只保存在本地 `.local/real-retrospective/` 和 `.local/real-asof/`，这些新运行的真实数据 HTML 和图表未加入公开包；README 单独展示的是原课程输出图。

拥有受信任的原算法和有权使用的历史行情时，可以重跑：

```bash
python scripts/compare_legacy.py \
  --legacy-metrics /path/to/original/src/window_metrics.py \
  --data /path/to/data/fast_test \
  --out .local/legacy-check.json
```

该脚本会执行指定的原 Python 文件，仅应使用可信本地代码。公开仓库未捆绑原算法压缩包与真实行情，因此**历史对照摘要不能在没有原始材料时独立复核**；公开合成演示、测试和浏览器脚本没有这个依赖。

## 图表与报告来源

- README 展示原课程的两张案例 PNG 和从研究报告第 4 页提取的图 1；不再以演示界面截图作为项目主图。
- `examples/report/` 包含同一次演示的输入、CSV、HTML、SVG/PNG 与哈希清单；可以逐项核对。
- 两张案例 PNG 与提供目录中的原文件逐字节一致；研究报告 PDF 与作者提供的原件逐字节一致。来源、提取方法与哈希见 [course-materials.json](evidence/course-materials.json)。
- 最高分案例属于事后挑选，仅用于解释；README 图像不是盈利证据。

## 尚未验证

没有大规模性能基准、完整交易所日历检查、样本外策略表现、交易成本模型、因果识别或其他平台兼容性实测。此次数值比对覆盖核心回顾评分，不是所有历史功能或 PPT 结论的完整复现。缺失窗口与分段边界等主动修改见[版本溯源](provenance.md)。
