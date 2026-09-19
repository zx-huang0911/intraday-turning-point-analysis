# 参与开发

请先读[方法定义](docs/methodology.md)和[数据卡](docs/data-card.md)。Issue 中说明版本、命令、预期与实际结果，尽量用合成数据复现；不要上传无授权行情、凭证或私人路径。

```bash
python -m venv .local/venv
source .local/venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
ruff format --check src tests scripts
```

修改公式或时间边界时，说明信息在哪个时点可获得，并补能区分新旧行为的测试。保留失败案例、缺失数据及实际验证范围，不用合成结果宣称市场收益。

`requirements-dev.lock` 是 Python 3.12 / Linux 的本地依赖快照；支持范围由 `pyproject.toml` 指定。浏览器检查是可选开发工具，不是运行分析的必要依赖，见 `scripts/check_report.py`。
