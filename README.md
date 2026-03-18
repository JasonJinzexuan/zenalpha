# ZenAlpha

基于缠论（缠中说禅技术分析理论）的量化信号识别平台。从原始 K 线出发，经过 10 层确定性算法管道，输出可追溯的买卖点信号。

## 定位

- **信号识别器**：自动执行 L0-L9 分析，输出 B1/B2/B3/S1/S2/S3 买卖信号
- **标的过滤器**：多标的扫描 → 评分排序 → Top N 输出
- **回测引擎**：事件驱动回测 + Walk-forward + Monte Carlo 验证

**不是**投资助手、不是交易系统、不接交易所 API。

## 快速开始

```bash
# 安装
git clone https://github.com/JasonJinzexuan/zenalpha.git
cd zenalpha
uv sync

# 分析
uv run zenalpha analyze AAPL --data data/aapl_daily.json

# 回测
uv run zenalpha backtest AAPL --data data/aapl_daily.json --start 2021-01-01 --end 2026-01-01

# 验证算法
uv run zenalpha validate tests/fixtures/

# 测试
uv run pytest tests/ -v
```

## 10 层算法管道

```
Raw K-Line
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  L0  包含关系处理    kline.py       纯规则，无歧义          │
│  L1  分型识别        fractal.py     顶/底分型 + 交替处理    │
│  L2  笔的划分        stroke.py      ≥5根K线 + 方向校验      │
│  MACD 增量计算       macd.py        EMA(12,26,9)            │
├─────────────────────────────────────────────────────────────┤
│  L3  线段划分        segment.py     特征序列 + 第二种情况    │
│  L4  中枢识别        center.py      ZG/ZD/GG/DD + 延伸/新生 │
│  L5  趋势分类        trend.py       盘整/上升/下降 + a+A+b+B+c │
│  L6  背驰判断        divergence.py  a段 vs c段 MACD面积     │
│  L7  买卖点生成      signal.py      B1/S1 + B2/S2 + B3/S3  │
│  L8  区间套          nesting.py     多级别递进定位           │
├─────────────────────────────────────────────────────────────┤
│  L9  评分排序        scorer.py      5维加权 + 过滤           │
│  L10 风控执行        position.py    ATR仓位 + 多层止损       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Signal / ScanResult
```

每层规则均对应缠论 108 课原文出处，详见 [docs/algorithm.md](docs/algorithm.md)。

## 项目结构

```
zenalpha/
├── chanquant/
│   ├── core/               # L0-L8 核心算法
│   │   ├── objects.py       # 所有数据结构 (frozen dataclass + Decimal)
│   │   ├── macd.py          # MACD/DIF/DEA 增量计算
│   │   ├── kline.py         # L0 包含关系处理
│   │   ├── fractal.py       # L1 分型识别
│   │   ├── stroke.py        # L2 笔的划分
│   │   ├── segment.py       # L3 线段划分 (含第二种情况)
│   │   ├── center.py        # L4 中枢识别
│   │   ├── trend.py         # L5 趋势与盘整分类
│   │   ├── divergence.py    # L6 背驰判断 (a vs c, 非 b vs c)
│   │   ├── signal.py        # L7 三类买卖点生成
│   │   ├── nesting.py       # L8 区间套 (确定性 fallback)
│   │   └── pipeline.py      # L0-L8 完整管道
│   ├── scoring/             # L9 评分层
│   │   ├── scorer.py        # 多维评分公式
│   │   └── filter.py        # 过滤 + 排序
│   ├── execution/           # L10 风控层 (实验性/仅限回测)
│   │   └── position.py      # ATR仓位计算 + 多层止损
│   ├── data/                # 数据接入层
│   │   ├── base.py          # DataSource Protocol
│   │   ├── polygon.py       # Polygon.io REST client
│   │   └── csv_loader.py    # CSV/JSON 加载器
│   ├── backtest/            # 回测引擎
│   │   ├── engine.py        # 事件驱动回测
│   │   ├── portfolio.py     # 不可变 Portfolio 状态
│   │   ├── slippage.py      # 滑点 + 佣金 + 市场冲击
│   │   ├── metrics.py       # Sharpe/Calmar/Sortino/MaxDD
│   │   └── walk_forward.py  # Walk-forward + Monte Carlo
│   └── cli/
│       └── main.py          # typer CLI (analyze/backtest/validate)
├── tests/
│   ├── fixtures/            # 测试用 K 线数据 (JSON)
│   └── unit/                # 59 个单元测试
├── docs/                    # 文档
│   ├── algorithm.md         # 算法规格 (10层详解)
│   └── architecture.md      # 架构设计
└── pyproject.toml
```

## 设计原则

| 原则 | 实现 |
|------|------|
| **Decimal 精度** | 所有价格/金融数值用 `Decimal`，核心算法无 `float` |
| **不可变数据** | 全部 `@dataclass(frozen=True)`，方法返回新对象 |
| **Feed-forward 流式** | 每个 Processor 有 `feed()` 方法，逐根 K 线增量计算 |
| **无外部依赖** | 核心算法仅用标准库 + Decimal，不依赖 pandas/numpy |
| **原文可追溯** | 每个信号附带 `source_lesson` 字段，映射缠论原文课号 |

## 关键修正（vs 常见开源实现）

1. **L3 线段第二种情况**：缺口 → 反向特征序列二次确认（多数实现遗漏）
2. **L6 背驰比较对象**：a 段 vs c 段（非 b vs c），原文第024课明确
3. **L6 c 段前提**：c 必须含对 B 中枢的第三类买卖点（第037课）
4. **L7 B2 三条件**：不创新低 / 盘整背驰 / 小转大（第053课）
5. **L8 区间套**：递进定位（非加权评分），原文第030课

## CLI 命令

### `zenalpha analyze`

单标的缠论结构分析，输出各层统计和信号。

```bash
uv run zenalpha analyze AAPL --level 1d --data path/to/data.json
```

### `zenalpha backtest`

事件驱动回测，输出 Sharpe/Sortino/Calmar/MaxDD 等指标。

```bash
uv run zenalpha backtest AAPL --data path/to/data.json \
  --start 2021-01-01 --end 2026-01-01 --cash 1000000
```

### `zenalpha validate`

用 fixture 数据验证 L0-L3 算法正确性。

```bash
uv run zenalpha validate tests/fixtures/
```

## 数据格式

输入数据为 JSON 数组，每条记录：

```json
{
  "timestamp": "2024-01-02T00:00:00",
  "open": 100.0,
  "high": 102.0,
  "low": 99.0,
  "close": 101.5,
  "volume": 1000000
}
```

也支持通过 `PolygonClient` 从 Polygon.io API 实时拉取。

## 技术栈

- Python 3.12+
- `uv` 包管理
- `httpx` — Polygon.io HTTP 客户端
- `typer` + `rich` — CLI
- `pytest` — 测试
- 无 pandas / numpy / ta-lib 依赖

## 开发路线

| Phase | 内容 | 状态 |
|-------|------|------|
| **0+1** | 10层算法管道 + 回测引擎 + CLI | **Done** |
| 2 | LLM Agent 编排 (LangGraph + Bedrock) | Planned |
| 3 | AWS CDK 部署 (Lambda + DynamoDB + EventBridge) | Planned |
| 4 | 前端 (Next.js + K线可视化) | Planned |
| 5 | 加密货币扩展 (Binance) | Planned |

## License

Private. All rights reserved.
