# ZenAlpha

基于缠论（缠中说禅技术分析理论）的量化信号识别与多级别结构分析平台。从原始 K 线出发，经过 10 层确定性算法管道，输出可追溯的买卖点信号，并通过区间套实现多级别递进定位。

## 定位

- **信号识别器**：自动执行 L0-L9 分析，输出一买/二买/三买/一卖/二卖/三卖买卖信号
- **标的过滤器**：多标的扫描 → 评分排序 → Top N 输出
- **区间套分析**：周线→日线→30分→5分，四级别递进定位操作点
- **LLM Agent 编排**：Claude tool_use + LangGraph，Agent 自主获取多级别数据并合成分析
- **实时数据流**：Polygon/Massive WebSocket 延迟行情 → InfluxDB → 15分钟缠论分析周期
- **回测引擎**：事件驱动回测 + 多级别区间套回测

**不是**投资助手、不是交易系统、不接交易所 API。

---

## 系统架构

```
                         ┌────────────────────────────────────────┐
                         │          CloudFront + WAF               │
                         │      React 18 SPA (前端终端)            │
                         │  TW Charts + Zustand + Tailwind CSS     │
                         └──────────────┬─────────────────────────┘
                                        │ HTTPS
                    ┌───────────────────▼─────────────────────────┐
                    │          Spring Cloud Gateway                 │
                    │       (JWT 验证 + 路由 + CORS)               │
                    │              port 8080                        │
                    └──┬────┬────┬────┬────┬────┬─────────────────┘
                       │    │    │    │    │    │
       ┌───────────────▼┐ ┌▼────▼┐ ┌▼────▼┐ ┌▼────▼──┐ ┌────────▼──┐
       │  agent-service  │ │signal│ │back- │ │ data   │ │  user     │
       │  (Python FastAPI│ │svc   │ │test  │ │service │ │ service   │
       │   缠论引擎)     │ │(Java)│ │svc   │ │(Java)  │ │ (JWT)     │
       │   port 8090     │ │8081  │ │8082  │ │ 8083   │ │  8084     │
       └──┬──────┬───────┘ └──┬───┘ └──┬───┘ └───┬────┘ └────┬─────┘
          │      │            │        │         │            │
   ┌──────▼──┐ ┌─▼────────┐  │        │         │            │
   │Bedrock  │ │ws-streamer│  └────────▼─────────▼────────────▼─────┐
   │ Claude  │ │ (Massive  │  │              RDS MySQL 8.0          │
   │ Sonnet  │ │  WebSocket│  └────────────────────────────────────┘
   └─────────┘ │  Delayed) │
               └──┬────────┘
                  │
          ┌───────▼────────┐
          │  InfluxDB v2   │
          │  (Timestream)  │
          │  K线 + OHLCV   │
          └───────┬────────┘
                  │
          ┌───────▼────────┐
          │  Polygon.io    │
          │  (行情数据源)   │
          └────────────────┘

     Eureka (服务注册)      Apollo (配置中心)      notification-service (8085)
```

### 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Lightweight Charts v5 |
| 状态管理 | Zustand (auth + watchlist) |
| API 网关 | Spring Cloud Gateway + JWT |
| 微服务 | Spring Boot 3.2 + Spring Cloud 2023 (Java 17) |
| 缠论引擎 | Python 3.12 + FastAPI + `chanquant` (核心算法库) |
| LLM Agent | Claude Sonnet (AWS Bedrock) + LangGraph + tool_use |
| 时序数据 | Amazon Timestream for InfluxDB (InfluxDB v2, Flux 查询) |
| 关系数据 | RDS MySQL 8.0 (用户、持仓、信号记录) |
| 行情数据 | Polygon/Massive REST + WebSocket (延迟15分钟) |
| 容器编排 | EKS (Kubernetes 1.29) |
| 前端部署 | CloudFront + S3 (OAC) + WAF |
| IaC | Terraform 1.7+ |

---

## 两套分析管道

系统提供**确定性管道**和**LLM Agent 管道**两套并行的分析路径：

### 确定性管道（L0-L8）

```
Raw K-Line
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  L0  包含关系处理    KLineProcessor       纯规则，无歧义        │
│  L1  分型识别        FractalDetector       顶/底分型 + 交替处理  │
│  L2  笔的划分        StrokeBuilder         ≥5根K线 + 方向校验    │
│  MACD 增量计算       MACDCalculator        EMA(12,26,9)          │
├─────────────────────────────────────────────────────────────────┤
│  L3  线段划分        SegmentBuilder        特征序列 + 第二种情况  │
│  L4  中枢识别        CenterDetector        ZG/ZD/GG/DD + 延伸    │
│  L5  趋势分类        TrendClassifier       盘整/上升/下降         │
│  L6  背驰判断        DivergenceDetector    a段 vs c段 MACD面积   │
│  L7  买卖点生成      SignalGenerator        一买/一卖 + 二/三买卖  │
│  L8  区间套          IntervalNester        多级别递进定位         │
├─────────────────────────────────────────────────────────────────┤
│  L9  评分排序        SignalScorer          5维加权 + 过滤         │
│  L10 风控执行        PositionSizer         ATR仓位 + 多层止损     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Signal / ScanResult
```

**这条管道是纯确定性的**：给定相同 K 线数据，永远产出相同结果。没有 LLM 参与。前端 `/overview`（态势总览）和 `/chart`（缠论图表）使用此管道。

#### 核心算法逻辑

| 层 | 输入 | 输出 | 关键逻辑 |
|----|------|------|---------|
| L0 | Raw K-Line | StandardKLine | 相邻K线包含关系处理（方向决定取高/取低） |
| L1 | StandardKLine | Fractal | 连续3根K线形成顶分型（中间最高）或底分型（中间最低） |
| L2 | Fractal | Stroke | 顶底分型之间≥5根K线，方向交替 |
| L3 | Stroke | Segment | **特征序列**分析：取反向笔构成序列，做包含处理后找分型。第一种终结（无缺口+分型）和第二种终结（缺口+反向分型确认） |
| L4 | Segment | Center | 3根线段重叠区间 [ZD, ZG]，后续线段仍在范围内则延伸 |
| L5 | Center[] | TrendType | 1个中枢=盘整，2+个非重叠递升中枢=上涨趋势，递降=下跌趋势。构建 a+A+b+B+c 结构 |
| L6 | TrendType + MACD | Divergence | 比较 a段 vs c段 MACD面积/DIF极值/量能衰竭，≥2/3确认=背驰 |
| L7 | Trend + Divergence + Centers | Signal[] | B1/S1=趋势背驰反转，B2/S2=不创新低/盘整背驰/小转大，B3/S3=突破中枢回踩不破 |

#### 关键修正（vs 常见开源实现）

| # | 层级 | 修正内容 | 原文依据 |
|---|------|---------|---------|
| 1 | L3 | 补充第二种情况（缺口 → 反向特征序列二次确认） | 第 067 课 |
| 2 | L3 | 线段方向由实际价格走势决定，非特征序列终结方向 | — |
| 3 | L4 | 移除中枢自动合并（`expand_centers`），保持独立中枢 | 第 017 课 |
| 4 | L5 | 滑动窗口趋势判定（最近2-3个中枢），非全部中枢 | 第 018 课 |
| 5 | L6 | 比较对象修正为 a 段 vs c 段（非 b vs c） | 第 024/037 课 |
| 6 | L6 | 无经典 a+A+b+B+c 结构时，fallback 到最近两个同向段比较 | — |
| 7 | L7 | 二买补充盘整背驰 + 小转大两个触发条件 | 第 053 课 |
| 8 | L7 | B3/S3 累积所有有效信号，不仅最后一个 | — |
| 9 | L7 | 信号按 (type, timestamp) 去重累积，非每轮覆盖 | — |
| 10 | L8 | 替换加权评分为区间套递进定位 | 第 030 课 |

#### 已知局限 & 待改进

| # | 层级 | 问题 | 影响 |
|---|------|------|------|
| 1 | L2 | 反方向分型不满足笔规则时丢弃原始起始分型 | 震荡行情笔可能缺失 |
| 2 | L6 | stagnation 与 area divergence 高度相关，三条件实质为两条件 | 背驰判断偏松 |
| 3 | L7 | B3/S3 基于笔级别突破（非段级别），且仅检查最后一个中枢 | B3/S3 信号偏多 |
| 4 | L7 | B2/S2 未限制在 B1 后第一次回调 | B2 可能远离实际二买位置 |

### LLM Agent 管道（LangGraph + Tool Use）

```
前端「一键分析」/「AI分析」
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 确定性 L0-L2 (与上面相同)                              │
│  KLineProcessor → FractalDetector → StrokeBuilder + MACD        │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: LLM Agent 链 (LangGraph StateGraph)                   │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ Segment  │──►│Structure │──►│Divergence│──►│ Signal   │     │
│  │  Agent   │   │  Agent   │   │  Agent   │   │  Agent   │     │
│  │(Sonnet)  │   │(Sonnet)  │   │(Sonnet)  │   │(Sonnet)  │     │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘     │
│       L3             L4-L5          L6              L7          │
│                                                     │            │
│                                              ┌──────▼─────┐     │
│                                              │  Nesting   │     │
│                                              │   Agent    │     │
│                                              │  (Sonnet)  │     │
│                                              │ + tool_use │     │
│                                              └────────────┘     │
│                                                    L8           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
LLM-enriched Analysis Result (stages + tool calls + reasoning)
```

#### Agent 的作用

**确定性管道已经能独立工作**。LLM Agent 管道的价值在于：

1. **L3 Segment Agent**：线段划分是缠论中最复杂的部分（特征序列 + 包含处理 + 两种终结），确定性算法处理边缘 case 可能有偏差，LLM 可以在上下文中综合判断
2. **L4-L5 Structure Agent**：中枢和趋势的判断需要整体结构视角（a+A+b+B+c），LLM 能用自然语言解释为什么归类为某种走势
3. **L6 Divergence Agent**：背驰判断有"三重确认"（面积/DIF/量能），LLM 能综合考虑市场状态而非机械比较数值
4. **L7 Signal Agent**：买卖点生成依赖前面所有层的判断，LLM 能做出更细腻的强度评估
5. **L8 Nesting Agent**（核心）：这是 Agent 最有价值的环节 —— 它使用 **tool_use** 自主调用工具：
   - `run_pipeline` — 对任意 instrument+timeframe 运行确定性 L0-L7
   - `compare_divergence` — 比较两个级别的背驰状态
   - `get_market_summary` — 获取全时间周期概览

   Agent 自主决定查看哪些级别、以什么顺序分析，然后合成区间套结论。

#### 条件路由

LangGraph pipeline 有条件边：
- 无线段 → 跳过 structure/divergence，直接到 signal（可能仍有 B3）
- 盘整（1个中枢）→ 跳过 divergence
- 无信号 → 跳过 nesting

#### Fallback 机制

NesterAgent 有三层 fallback：
1. **LLM tool_use** → 自主多级别分析（最佳）
2. **确定性多级别** → 依次跑 1w/1d/30m/5m pipeline 并合成（无 LLM）
3. **确定性单级别** → 仅从已有扫描结果推断（最简）

如果 Bedrock 不可用或 LLM 调用失败，自动降级到确定性路径。

---

## 数据管道

### 三种数据获取方式

```
                  ┌─────────────┐
                  │  Polygon.io │
                  └──┬──────┬───┘
                     │      │
              REST API    WebSocket (Massive SDK)
              (按需)      (实时, 延迟15min)
                     │      │
                     ▼      ▼
    ┌───────────────────────────────────────────────┐
    │              InfluxDB (Timestream)              │
    │  bucket: marketdata                             │
    │  measurement: kline                             │
    │  tags: instrument, timeframe                    │
    │  fields: open, high, low, close, volume         │
    └───────────────────────────────────────────────┘
```

| 方式 | 触发 | 数据 | 说明 |
|------|------|------|------|
| **WebSocket Streamer** | 持续运行 | 1m → 5m/30m/1h 实时聚合 | `ws-streamer` Deployment，使用 Massive SDK `Feed.Delayed`，每15分钟自动跑缠论分析 |
| **CronJob Sync** | `*/15 13-20 * * 1-5` | 1d + 1w 增量同步 | 美股盘中每15分钟，仅同步日线和周线（分钟级由 WS 处理） |
| **手动/API Ingest** | 前端设置页 / API 调用 | 任意级别 | `POST /ingest/sync` 增量、`POST /ingest/bulk` 全量 |

### WS Streamer 细节

`chanquant/data/ws_stream.py`:

1. 订阅 19 只标的的 `AM.*`（分钟聚合）
2. 每根1分钟 bar → 写入 InfluxDB + 聚合到 5m/30m/1h
3. 聚合逻辑：`BarAggregator` 在 `(hour*60 + minute + 1) % period == 0` 时 flush
4. 每15分钟 → 后台线程跑 `execute_tool("run_pipeline")` 对19只标的做缠论分析
5. 断线重连：指数退避（1s → 5min），最多20次

### 不会重复写入

- InfluxDB 写入是幂等的（相同 measurement+tags+timestamp 覆盖）
- WS 处理盘中分钟级数据 (1m/5m/30m/1h)
- CronJob 只处理 1d + 1w
- 无重叠

---

## 前端页面

| 页面 | 路由 | 数据管道 | 功能 |
|------|------|---------|------|
| **态势总览** | `/overview` | 确定性 | 多标的扫描状态矩阵，走势状态一览，实时数据流状态指示器 |
| **信号分析** | `/signals` | 确定性 | 4级别 K 线图 (1w/1d/30m/5m) 并排显示 + 信号类型过滤 (B1-S3) + 信号时间线 |
| **区间套地图** | `/nesting-map/:symbol` | 确定性 + LLM | 4层级递进分析 + **AI分析按钮**（调用 NesterAgent tool_use） |
| **策略实验室** | `/strategy` | 确定性 | 策略参数/风控参数分离配置 + 标的选择器 + 回测结果 + 敏感度分析 |
| **自选管理** | `/watchlist` | — | 自选列表管理 + 标的搜索添加 |
| **通知中心** | `/notifications` | — | 信号通知记录 |
| **LLM Pipeline** | `/pipeline` | LLM Agent | 一键触发 LangGraph 多Agent分析，Stage时间线，Tool Call展示 |
| **持仓管理** | `/positions` | — | 多级别走势状态标签，操作提示 |
| **信号回顾** | `/review` | — | 正确/错误/待定分组 |
| **回测实验** | `/backtest` | 确定性 | Sharpe/Sortino/MaxDD + 权益曲线 |
| **设置** | `/settings` | — | 手动数据同步 |

---

## REST API

### Agent Service (Python FastAPI, port 8090)

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/health` | 健康检查 + InfluxDB 连接状态 |
| `GET` | `/klines/{instrument}?level=1d&limit=500` | 从 InfluxDB 获取 K 线 |
| `POST` | `/analyze` | 传入 K 线 → 确定性 L0-L8 管道 |
| `POST` | `/scan` | 多标的批量扫描（InfluxDB → Pipeline） |
| `POST` | `/nesting/analyze` | **NesterAgent tool_use 区间套分析** |
| `POST` | `/pipeline/trigger` | **触发 LangGraph LLM Pipeline**（异步） |
| `GET` | `/pipeline/status` | 查询 Pipeline 进度和结果 |
| `POST` | `/ingest` | 单标的 Polygon → InfluxDB |
| `POST` | `/ingest/bulk` | 全量批量拉取 |
| `POST` | `/ingest/sync` | **增量同步**（基于 last timestamp） |
| `POST` | `/backtest` | 事件驱动回测 |
| `POST` | `/backtest/nesting` | 多级别区间套回测 |
| `POST` | `/strategy/backtest` | **策略回测**（strategy + risk 参数分离） |
| `POST` | `/strategy/sensitivity` | 参数敏感度分析 |
| `POST` | `/strategy/save` | 保存策略配置 |
| `GET` | `/strategy/list` | 已保存策略列表 |
| `POST` | `/decision/run` | 运行决策引擎 |

### 安全

- API 端点有**速率限制**（60/min 一般，10/min 重操作）
- Instrument 参数白名单校验（`^[A-Z0-9]{1,10}$`）
- Timeframe 枚举校验
- InfluxDB Flux 查询参数防注入
- LLM 响应 JSON 通过 Pydantic schema 校验
- WebSocket 断线指数退避 + 最大重试次数

---

## Agent 工具定义

NesterAgent 和 WS Streamer 的分析循环使用以下 3 个工具：

| 工具 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `run_pipeline` | instrument, timeframe, limit | trend, centers, divergences, signals | 运行确定性 L0-L7 管道 |
| `compare_divergence` | instrument, large_tf, small_tf | 两个级别的背驰对比 + alignment | 判断大小级别是否共振 |
| `get_market_summary` | instrument | 4个级别 (1w/1d/30m/5m) 的概览 | 一次调用获取全局视图 |

Agent 执行循环（`tool_executor.py`）：
1. 构建 system prompt + user message
2. `model.bind_tools(tools)` 绑定工具
3. LLM 返回 `tool_use` → 执行 → 结果反馈 → 再次调用 LLM
4. 最多 8 轮迭代，直到 LLM 不再调用工具
5. 解析最终 JSON 响应

---

## 项目结构

```
zenalpha/
├── frontend/                          # React 18 SPA
│   ├── src/
│   │   ├── pages/                     # 态势总览, 信号分析, 区间套, 策略实验室, Pipeline...
│   │   ├── components/chart/          # ChanChart (6层叠加 + MACD子图 + 信号标记)
│   │   ├── stores/                    # Zustand (auth, watchlist, strategy)
│   │   ├── api/                       # agent.ts, data.ts, auth.ts
│   │   └── types/                     # chan.ts, api.ts
│
├── chanquant/                         # Python 缠论核心库
│   ├── core/
│   │   ├── objects.py                 # 不可变数据类: RawKLine, Fractal, Stroke, Segment, Center...
│   │   ├── pipeline.py                # AnalysisPipeline (确定性 L0-L8)
│   │   ├── kline.py                   # L0 包含关系处理
│   │   ├── fractal.py                 # L1 分型识别
│   │   ├── stroke.py                  # L2 笔的划分
│   │   ├── segment.py                 # L3 线段划分 (特征序列)
│   │   ├── center.py                  # L4 中枢识别 (重叠+延伸+扩展)
│   │   ├── trend.py                   # L5 趋势分类 (a+A+b+B+c)
│   │   ├── divergence.py              # L6 背驰判断 (面积/DIF/量能 三重确认)
│   │   ├── signal.py                  # L7 买卖点 (B1-B3, S1-S3)
│   │   ├── nesting.py                 # L8 区间套
│   │   └── macd.py                    # MACD 增量计算
│   ├── agents/
│   │   ├── langgraph_pipeline.py      # LangGraph LLM Pipeline (L3-L8 Agent 链)
│   │   ├── nester.py                  # NesterAgent (tool_use + 3层fallback)
│   │   ├── decision.py                # 决策引擎 (信号 → 交易决策)
│   │   ├── tool_defs.py               # 3个工具定义 + 执行器
│   │   ├── tool_executor.py           # Agentic loop (invoke→tool→result→repeat)
│   │   ├── bedrock.py                 # Bedrock model factory (Claude Sonnet)
│   │   └── prompts.py                 # Agent prompt 加载
│   ├── strategy/                      # 策略模块
│   │   └── ...                        # 策略定义 + 参数优化
│   ├── risk/                          # 风控模块
│   │   └── ...                        # 仓位管理 + 止损
│   ├── api/
│   │   ├── gateway.py                 # FastAPI (REST + 速率限制 + 输入校验)
│   │   └── strategy_routes.py         # 策略回测 + 敏感度分析 API
│   ├── data/
│   │   ├── timestream.py              # InfluxDB 客户端 (白名单防注入)
│   │   ├── polygon.py                 # Polygon REST 客户端
│   │   └── ws_stream.py              # WebSocket 实时流 (聚合 + 分析 + 重连)
│   └── backtest/
│       ├── engine.py                  # 事件驱动回测
│       └── nesting_engine.py          # 多级别区间套回测
│
├── services/                          # Java 微服务
│   ├── gateway/                       # API 网关 + JWT
│   ├── signal-service/                # 信号持久化
│   ├── data-service/                  # 标的管理
│   ├── user-service/                  # 认证 + Watchlist
│   └── ...
│
├── terraform/                         # AWS IaC
│   ├── modules/
│   │   ├── vpc/                       # 3 AZ, public/private subnets
│   │   ├── eks/                       # EKS 1.29
│   │   ├── rds/                       # MySQL 8.0
│   │   ├── timestream/                # Amazon Timestream for InfluxDB
│   │   └── frontend/                  # S3 + CloudFront (OAC) + WAF
│   └── k8s/
│       ├── agent-service/             # Deployment + ws-streamer + CronJobs
│       └── ...
│
├── scripts/
│   ├── deploy-k8s.sh                 # K8s 部署脚本
│   └── bulk_ingest.py                # 一次性历史数据导入
│
├── Dockerfile.agent                   # Python agent-service 多阶段构建
└── docs/
    └── algorithm.md                   # 算法规格 (10层详解 + 修正说明)
```

---

## 设计原则

| 原则 | 实现 |
|------|------|
| **BigDecimal 精度** | 所有价格/金融数值用 `Decimal`，核心算法无 `float` |
| **不可变数据** | Python `@dataclass(frozen=True)` + `NamedTuple` |
| **确定性优先** | 核心管道纯确定性，LLM 是增强而非替代 |
| **优雅降级** | LLM 不可用时自动 fallback 到确定性路径 |
| **幂等写入** | InfluxDB 相同 tags+timestamp 覆盖，不产生重复 |
| **原文可追溯** | 每个信号附带 `source_lesson` 字段 |
| **IaC** | 全部基础设施 Terraform 管理 |

---

## 快速开始

### 本地开发

```bash
git clone https://github.com/JasonJinzexuan/zenalpha.git
cd zenalpha

# 前端 — 需要 Node 18+
cd frontend
npm ci
npm run dev         # http://localhost:5173

# Python 缠论引擎 — 需要 Python 3.12+
cd ..
pip install -e ".[api,agents,streaming]"
uvicorn chanquant.api.gateway:app --port 8090
```

### 一键部署（AWS）

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
cat > secrets.auto.tfvars << 'EOF'
db_password        = "<strong-password>"
influxdb_password  = "<strong-password>"
influxdb_api_token = "<created-after-influxdb-init>"
polygon_api_key    = "<your-key>"
EOF

terraform init && terraform apply
aws eks update-kubeconfig --name zenalpha-prod-eks --region us-west-2
scripts/build-all.sh
scripts/deploy-k8s.sh
```

### 前端部署

```bash
cd frontend
npm run build
aws s3 sync dist/ s3://zenalpha-prod-frontend/ --delete
aws s3 cp dist/index.html s3://zenalpha-prod-frontend/index.html \
  --cache-control "no-cache, no-store, must-revalidate"
aws cloudfront create-invalidation --distribution-id E2AYS09PAJLLZD --paths "/*"
```

---

## 开发路线

| Phase | 内容 | 状态 |
|-------|------|------|
| **0+1** | 10 层确定性算法管道 + 回测引擎 + Python CLI | ✅ Done |
| **2** | Java 微服务 + Terraform + K8s | ✅ Done |
| **3** | React 前端 + InfluxDB 时序存储 + agent-service | ✅ Done |
| **4** | LLM Agent 编排 (LangGraph + Bedrock + tool_use) | ✅ Done |
| **4.5** | 实时数据流 (Massive WebSocket + 聚合 + 15min分析) | ✅ Done |
| **5** | 信号分析页 + 策略实验室 + 缠论引擎修正 | ✅ Done |
| 6 | 加密货币扩展 (Binance WebSocket) | Planned |
| 7 | 实时信号推送 (WebSocket + SNS) | Planned |

---

## 缠论术语映射

| 代号 | 中文 | 英文 |
|------|------|------|
| B1 | 一买 | First Buy Point |
| B2 | 二买 | Second Buy Point |
| B3 | 三买 | Third Buy Point |
| S1 | 一卖 | First Sell Point |
| S2 | 二卖 | Second Sell Point |
| S3 | 三卖 | Third Sell Point |

## License

Private. All rights reserved.
