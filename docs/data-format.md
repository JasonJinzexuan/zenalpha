# 数据格式规范

## 输入数据

### JSON 格式 (推荐)

```json
[
  {
    "timestamp": "2024-01-02T00:00:00",
    "open": 100.0,
    "high": 102.0,
    "low": 99.0,
    "close": 101.5,
    "volume": 1000000
  },
  ...
]
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | string | ISO 8601 格式，必须包含日期部分 |
| `open` | number | 开盘价 |
| `high` | number | 最高价 |
| `low` | number | 最低价 |
| `close` | number | 收盘价 |
| `volume` | integer | 成交量 |

### CSV 格式

```csv
timestamp,open,high,low,close,volume
2024-01-02T00:00:00,100.0,102.0,99.0,101.5,1000000
```

首行为表头，逗号分隔。

### Polygon.io API

通过 `PolygonClient` 自动拉取：

```python
from chanquant.data.polygon import PolygonClient
from chanquant.core.objects import TimeFrame

client = PolygonClient(api_key="your_key")
klines = await client.get_klines("AAPL", TimeFrame.DAILY, limit=500)
```

## 输出数据

### PipelineState

`pipeline.feed()` 返回的完整状态快照：

| 字段 | 类型 | 说明 |
|------|------|------|
| `standard_klines` | `tuple[StandardKLine, ...]` | L0 输出的标准化 K 线 |
| `fractals` | `tuple[Fractal, ...]` | L1 识别的分型 |
| `strokes` | `tuple[Stroke, ...]` | L2 划分的笔 |
| `segments` | `tuple[Segment, ...]` | L3 划分的线段 |
| `centers` | `tuple[Center, ...]` | L4 识别的中枢 |
| `trend` | `TrendType \| None` | L5 趋势分类 |
| `divergences` | `tuple[Divergence, ...]` | L6 背驰结果 |
| `signals` | `tuple[Signal, ...]` | L7 买卖点信号 |
| `macd_values` | `tuple[MACDValue, ...]` | MACD 指标值 |

### Signal

```python
@dataclass(frozen=True)
class Signal:
    signal_type: SignalType   # B1/B2/B3/S1/S2/S3
    level: TimeFrame          # 信号级别
    instrument: str           # 标的代码
    timestamp: datetime       # 信号时间
    price: Decimal            # 信号价格
    strength: Decimal         # 信号强度 [0, 1]
    source_lesson: str        # 原文课号
    reasoning: str            # 判断理由
```

### BacktestMetrics

```python
@dataclass(frozen=True)
class BacktestMetrics:
    total_return: Decimal         # 总收益率
    annualized_return: Decimal    # 年化收益率
    sharpe_ratio: Decimal         # Sharpe 比率
    sortino_ratio: Decimal        # Sortino 比率
    calmar_ratio: Decimal         # Calmar 比率
    max_drawdown: Decimal         # 最大回撤
    win_rate: Decimal             # 胜率
    profit_factor: Decimal        # 盈亏比
    total_trades: int             # 总交易次数
```

## 测试数据

`tests/fixtures/` 目录包含三种行情：

| 文件 | 行情类型 | K 线数 | 用途 |
|------|---------|--------|------|
| `uptrend.json` | 上涨趋势 | 30 | 测试向上笔/线段/中枢 |
| `downtrend.json` | 下跌趋势 | 30 | 测试向下结构 |
| `consolidation.json` | 盘整震荡 | 30 | 测试中枢延伸/盘整背驰 |
