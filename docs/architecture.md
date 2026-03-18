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

## 扩展路径

### Phase 2: LLM Agent 编排

```
pipeline.py 的 L3-L8 各层增加 LLM fallback:
  代码先做确定性判断
  → 边界 case 时调用 LLM Agent 仲裁
  → Agent 返回带 reasoning 的判断

LangGraph State Schema:
  每层 Agent 读写共享 state
  Supervisor 控制路由
```

### Phase 3: AWS 部署

```
EventBridge (cron) → Lambda (pipeline) → DynamoDB (signals)
                                       → SNS (告警)
API Gateway → Lambda → DynamoDB (查询)
```

### Phase 4: 前端

```
Next.js + Lightweight Charts
K 线图上叠加: 笔/线段/中枢/信号标注
实时 WebSocket 推送新信号
```
