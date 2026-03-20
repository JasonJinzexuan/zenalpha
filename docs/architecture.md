# 架构设计

## 整体架构

```
                    ┌──────────────┐
                    │   CLI / API  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌────────────┐ ┌────────┐ ┌──────────┐
       │  Pipeline   │ │ Scorer │ │ Backtest │
       │  (L0-L8)   │ │ (L9)   │ │ Engine   │
       └──────┬─────┘ └───┬────┘ └────┬─────┘
              │            │           │
              ▼            ▼           ▼
       ┌─────────────────────────────────────┐
       │           core/objects.py            │
       │    (frozen dataclass + Decimal)      │
       └──────────────────┬──────────────────┘
                          │
                ┌─────────┼─────────┐
                ▼                   ▼
         ┌────────────┐     ┌────────────┐
         │ Polygon.io │     │ CSV/JSON   │
         │ Client     │     │ Loader     │
         └────────────┘     └────────────┘
```

## 核心设计模式

### 1. Feed-forward 流式处理

每个 Processor 类维护内部状态，通过 `feed()` 方法逐根 K 线增量处理：

```python
class KLineProcessor:
    def feed(self, raw: RawKLine) -> StandardKLine | None: ...

class FractalDetector:
    def feed(self, kline: StandardKLine) -> Fractal | None: ...

class StrokeBuilder:
    def feed(self, fractal: Fractal) -> Stroke | None: ...
```

优势：
- 适合实时流数据（WebSocket 行情）
- 内存占用恒定，不随数据量增长
- 每个 Processor 可独立测试

### 2. 不可变数据流

所有数据对象使用 `@dataclass(frozen=True)`：

```python
@dataclass(frozen=True)
class StandardKLine:
    timestamp: datetime
    high: Decimal
    low: Decimal
    ...
```

规则：
- Processor 内部可维护 `list` 做缓冲
- 对外返回值必须是不可变对象或 `tuple`
- 创建新状态用 `dataclasses.replace()` 或构造新实例
- `PipelineState` 中所有集合类型均为 `tuple`

### 3. Decimal 精度

金融计算全部使用 `Decimal`：

```python
price = Decimal("150.25")  # 正确
price = 150.25             # 禁止
```

唯一例外：`macd.py` 内部 EMA 计算使用 `float`（性能考虑），输出转回 `Decimal`。

验证方法：
```bash
grep -r '\bfloat\b' chanquant/core/ --include='*.py'
# 应仅出现在 macd.py
```

## 模块依赖关系

```
objects.py (零依赖，所有类型定义)
    ▲
    │
macd.py ──────────────────────────────────────┐
    ▲                                          │
    │                                          │
kline.py                                       │
    ▲                                          │
    │                                          │
fractal.py                                     │
    ▲                                          │
    │                                          │
stroke.py ◄────────────────────────────────────┘
    ▲
    │
segment.py
    ▲
    │
center.py
    ▲
    │
trend.py
    ▲
    │
divergence.py ◄── macd.py (MACD面积比较)
    ▲
    │
signal.py
    ▲
    │
nesting.py
    ▲
    │
pipeline.py ◄── 串联以上所有
```

## Pipeline 数据流

`AnalysisPipeline.feed(raw_kline)` 内部流程：

```
1. MACD: raw.close → IncrementalMACD → MACDValue
2. L0:   raw → KLineProcessor → StandardKLine | None
   (若 None，即被合并，直接返回当前 state)
3. L1:   StandardKLine → FractalDetector → Fractal | None
4. L2:   Fractal → StrokeBuilder → Stroke | None
   附加 MACD 面积: attach_macd_area(stroke, macd_values)
5. L3:   Stroke → SegmentBuilder → Segment | None
6. L4:   Segment → CenterDetector → Center | None
7. L5:   (centers, segments) → TrendClassifier → TrendType
8. L6:   (trend, macd_values) → DivergenceDetector → Divergence | None
9. L7:   (trend, divergence, centers) → SignalGenerator → list[Signal]
10. 返回 PipelineState 快照
```

每一步若返回 `None`，后续步骤不执行（数据还不够形成结构）。

## 回测引擎架构

```
BacktestEngine.run(klines_by_instrument)
    │
    ├── for each bar:
    │   ├── Pipeline.feed(bar) → signals
    │   ├── StopLossManager.check_stops() → exit signals
    │   ├── PositionSizer.calculate_size() → position size
    │   ├── SlippageModel.apply() → adjusted price
    │   ├── PortfolioManager.open/close_position() → new snapshot
    │   └── Record snapshot
    │
    └── calculate_metrics(snapshots, trades) → BacktestMetrics
```

### 滑点模型

```
adjusted_price = ideal_price × (1 + slippage)

slippage = tier_slippage + market_impact
  tier_slippage: large_cap 0.01%, mid_cap 0.03%, small_cap 0.05%
  market_impact: sqrt(order_qty / avg_volume) × volatility × price

commission = max($1, shares × $0.005)
```

### Walk-forward 验证

```
|----train1----|--test1--|
     |----train2----|--test2--|
          |----train3----|--test3--|

n_splits = 5, train_ratio = 0.7
每个 window 独立跑回测，输出各自 metrics
```

### Monte Carlo

```
1. 取所有 trades
2. 随机打乱顺序 × 1000 次
3. 每次计算最终权益
4. 统计 p-value 和置信区间
```

## 数据层设计

### DataSource Protocol

```python
class DataSource(Protocol):
    async def get_klines(
        self, instrument: str, timeframe: TimeFrame, limit: int = 500
    ) -> Sequence[RawKLine]: ...

    async def get_instruments(self) -> Sequence[str]: ...
```

### Polygon.io 客户端

- 指数退避重试: 3 次, 1s → 2s → 4s
- TimeFrame 映射到 Polygon API 参数
- 自动转换 Unix timestamp → datetime

### CSV/JSON 加载器

- 支持 CSV (columns: timestamp,open,high,low,close,volume)
- 支持 JSON (同 CLI 输入格式)
- 自动解析 ISO 8601 时间戳

## LangGraph LLM Pipeline（已实现）

L0-L2 保持确定性算法，L3-L8 替换为 LLM Agent，通过 LangGraph StateGraph 编排。

### 架构

```
Phase 1: 确定性计算                    Phase 2: LLM Agent (LangGraph)
┌─────────────────────────┐           ┌──────────────────────────────────────────┐
│ RawKLine                │           │                                          │
│   → L0 K线合并          │           │  ┌──────────┐  条件路由  ┌────────────┐  │
│   → L1 分型检测          │  state   │  │ L3 线段   ├──────────▶│ L4-L5 中枢  │  │
│   → L2 笔构建+MACD面积   ├─────────▶│  │ Agent    │  有线段    │ +走势 Agent │  │
│                          │           │  └──────────┘           └──────┬─────┘  │
└─────────────────────────┘           │       │ 无线段                  │        │
                                       │       ▼                 有趋势  │ 无趋势 │
                                       │  ┌──────────┐    ┌────────────┘        │
                                       │  │ L7 信号   │◀───┤                     │
                                       │  │ Agent    │    │  ┌──────────┐       │
                                       │  └────┬─────┘    └──┤ L6 背驰  │       │
                                       │       │ 有信号      │ Agent    │       │
                                       │       ▼             └──────────┘       │
                                       │  ┌──────────┐                          │
                                       │  │ L8 区间套 │                          │
                                       │  │ Agent    │                          │
                                       │  └──────────┘                          │
                                       └──────────────────────────────────────────┘
```

### 共享状态

```python
class LLMPipelineState(TypedDict, total=False):
    instrument: str
    level: str
    standard_klines: list[dict]    # L0-L2 输出
    fractals: list[dict]
    strokes: list[dict]
    macd_values: list[dict]
    segments: list[dict]           # L3 Agent 输出
    centers: list[dict]            # L4-L5 Agent 输出
    trend: dict | None
    divergence: dict | None        # L6 Agent 输出
    signals: list[dict]            # L7 Agent 输出
    nesting: dict | None           # L8 Agent 输出
    errors: list[str]
```

### 模型配置

所有 Agent 使用 Claude Sonnet 4.6 via AWS Bedrock (inference profile)：

| Agent | Model ID | 用途 |
|-------|----------|------|
| segment-agent | `global.anthropic.claude-sonnet-4-6` | 线段终结判断 |
| structure-agent | `global.anthropic.claude-sonnet-4-6` | 中枢检测+走势分类 |
| divergence-agent | `global.anthropic.claude-sonnet-4-6` | MACD背驰判断 |
| signal-agent | `global.anthropic.claude-sonnet-4-6` | 买卖点信号生成 |
| nesting-agent | `global.anthropic.claude-sonnet-4-6` | 多级别区间套 |

### 条件路由

- `segment → structure`: 有线段则进入中枢分析，否则跳到信号
- `structure → divergence`: 有趋势（UP/DOWN）则检测背驰，盘整跳到信号
- `signal → nesting`: 有信号则进入区间套，否则结束

### 关键实现

- **JSON-only 输出**: 系统提示末尾追加 `_JSON_SUFFIX` 强制 LLM 返回纯 JSON
- **JSON 提取**: `_extract_json()` 处理 markdown code block、trailing comma、单引号
- **异步执行**: `asyncio.to_thread()` 防止同步 LLM 调用阻塞 uvicorn 事件循环
- **Stage 追踪**: `run_llm_analysis_with_stages()` 记录每个节点的输入摘要、输出 diff、耗时

### API 端点

| 端点 | 说明 |
|------|------|
| `GET /analyze/langgraph/{instrument}` | 运行 LLM Pipeline，返回最终结果 |
| `GET /analyze/langgraph/{instrument}/stages` | 运行 Pipeline + 返回每阶段输入/输出/耗时 |

### 前端 Pipeline 可视化

`/pipeline` 页面展示 LangGraph 执行全过程：
- 每个 stage 可展开查看 INPUT/OUTPUT JSON
- Timeline 时间条按耗时比例着色
- 最终输出（signals, segments, centers 等）可折叠查看

## 数据同步架构

### 多级别数据源

区间套分析需要 4 个级别的 K 线数据，全部存储在 InfluxDB (Timestream)：

| 级别 | 角色 | 回填深度 | 说明 |
|------|------|---------|------|
| 1w | 方向层 | 4 年 | 判断大方向 |
| 1d | 位置层 | 2 年 | 判断当前位置 |
| 30m | 精确层 | 60 天 | 精确买卖点 |
| 5m | 操作层 | 14 天 | 入场时机 |

### 数据流

```
Polygon.io REST API
        │
        ├── 初始回填: scripts/sync_polygon_influxdb.py --backfill
        │   (本地或集群内运行，需连 InfluxDB VPC)
        │
        ├── 每日增量: CronJob (UTC 01:00)
        │   curl → agent-service /ingest/bulk
        │   19 instruments × 5 timeframes, 13s/req (Polygon free tier)
        │
        └── 手动单个: POST /ingest
            {instrument, level, limit}
```

### Polygon Rate Limit

- Free tier: 5 requests/minute
- `polygon.py` retry: 5 次, backoff 从 13s 起
- `/ingest/bulk` 端点: 每次请求间隔 13s
- CronJob `activeDeadlineSeconds: 1800` (30 分钟)

## 部署架构（已实现）

```
┌──────────────── AWS Cloud ────────────────────────────────────────┐
│                                                                    │
│  CloudFront + WAF ──── S3 (React SPA)                             │
│       │                                                            │
│       │ /api/*                                                     │
│       ▼                                                            │
│  ALB (K8s LoadBalancer Service)                                    │
│       │                                                            │
│  ┌────▼──── EKS 集群 ────────────────────────────────────────┐    │
│  │                                                            │    │
│  │  agent-service (Python FastAPI)                            │    │
│  │    ├── 缠论引擎 (L0-L2 确定性)                            │    │
│  │    ├── LangGraph LLM Pipeline (L3-L8 Agent)               │    │
│  │    ├── /ingest + /ingest/bulk (Polygon → InfluxDB)        │    │
│  │    └── CronJob: daily-ingest (UTC 01:00)                  │    │
│  │                                                            │    │
│  │  Spring Cloud 微服务 (gateway, user, data, signal, ...)   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  RDS MySQL 8.0          Timestream InfluxDB v2                    │
│  (关系型数据)            (OHLCV K线 × 5级别)                      │
│                                                                    │
│  Bedrock (Claude Sonnet 4.6, inference profile)                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```
