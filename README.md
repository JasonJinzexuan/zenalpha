# ZenAlpha

基于缠论（缠中说禅技术分析理论）的量化信号识别与多级别结构分析平台。从原始 K 线出发，经过 10 层确定性算法管道，输出可追溯的买卖点信号，并通过区间套实现多级别递进定位。

## 定位

- **信号识别器**：自动执行 L0-L9 分析，输出一买/二买/三买/一卖/二卖/三卖买卖信号
- **标的过滤器**：多标的扫描 → 评分排序 → Top N 输出
- **区间套分析**：周线→日线→30分→5分，四级别递进定位操作点
- **回测引擎**：事件驱动回测 + Walk-forward + Monte Carlo 验证

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
       └───────┬─────────┘ └──┬───┘ └──┬───┘ └───┬────┘ └────┬─────┘
               │              │        │         │            │
      ┌────────▼──────┐  ┌───▼────────▼─────────▼────────────▼─────┐
      │  InfluxDB v2   │  │              RDS MySQL 8.0               │
      │  (Timestream)  │  │  (instrument, signal, backtest, user)   │
      │  K线 + OHLCV   │  └────────────────────────────────────────┘
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
| 时序数据 | Amazon Timestream for InfluxDB (InfluxDB v2, Flux 查询) |
| 关系数据 | RDS MySQL 8.0 (用户、持仓、信号记录) |
| 行情数据 | Polygon.io REST API → InfluxDB |
| 注册中心 | Eureka Server |
| 配置中心 | Apollo Config |
| 容器编排 | EKS (Kubernetes 1.29) |
| 前端部署 | CloudFront + S3 (OAC) + WAF |
| IaC | Terraform 1.7+ |
| 定时任务 | K8s CronJob (每日 UTC 01:00 自动 ingest + scan) |

---

## 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| **态势总览** | `/overview` | 多标的扫描状态矩阵，走势状态（上涨/下跌/盘整/背驰）一览，紧急/关注信号分组 |
| **区间套地图** | `/nesting-map/:symbol` | 4 层级递进分析：周线(方向)→日线(位置)→30分(精确)→5分(操作)，综合结论 |
| **缠论图表** | `/chart/:symbol` | 交互式 K 线图 + 6 层叠加（分型/笔/线段/中枢/买卖点/背驰）+ MACD 子图 |
| **持仓管理** | `/positions` | 多级别走势状态标签，操作提示（定理8.5/10.2/10.3），成本归零进度 |
| **信号回顾** | `/review` | 正确/错误/待定分组，点击查看明细（结构快照/MAE/MFE/失败原因/经验教训） |
| **回测实验** | `/backtest` | 配置表单 + 指标卡片 (Sharpe/Sortino/MaxDD) + 权益曲线 |
| **设置** | `/settings` | 自选列表管理，手动/自动 ingest 数据同步 |

### 图表叠加层

| 叠加层 | 说明 |
|--------|------|
| 分型 | 顶分型（橙色 ▽）/ 底分型（青色 △） |
| 笔 | 蓝色连线，连接相邻顶底分型 |
| 线段 | 紫色粗线，至少 3 笔构成 |
| 中枢 | 黄色虚线标注 ZG/ZD 区间 |
| 买卖点 | 绿色（买入）/ 红色（卖出）标记 |
| 背驰 | a 段 vs c 段 MACD 面积对比区域 |

### 缠论术语映射

| 代号 | 中文 | 英文 |
|------|------|------|
| B1 | 一买 | First Buy Point |
| B2 | 二买 | Second Buy Point |
| B3 | 三买 | Third Buy Point |
| S1 | 一卖 | First Sell Point |
| S2 | 二卖 | Second Sell Point |
| S3 | 三卖 | Third Sell Point |

---

## 10 层算法管道

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
│  L7  买卖点生成      SignalGenerator       一买/一卖 + 二/三买卖  │
│  L8  区间套          IntervalNester        多级别递进定位         │
├─────────────────────────────────────────────────────────────────┤
│  L9  评分排序        SignalScorer          5维加权 + 过滤         │
│  L10 风控执行        PositionSizer         ATR仓位 + 多层止损     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Signal / ScanResult
```

每层规则均对应缠论 108 课原文出处，详见 [docs/algorithm.md](docs/algorithm.md)。

### 关键修正（vs 常见开源实现）

| # | 层级 | 修正内容 | 原文依据 |
|---|------|---------|---------|
| 1 | L3 | 补充第二种情况（缺口 → 反向特征序列二次确认） | 第 067 课 |
| 2 | L6 | 比较对象修正为 a 段 vs c 段（非 b vs c） | 第 024/037 课 |
| 3 | L6 | c 段必须含对 B 中枢的第三类买卖点 | 第 037 课 |
| 4 | L7 | 二买补充盘整背驰 + 小转大两个触发条件 | 第 053 课 |
| 5 | L8 | 替换加权评分为区间套递进定位 | 第 030 课 |

---

## 数据流

### K 线数据

```
Polygon.io  ──(REST API)──►  agent-service /ingest  ──►  InfluxDB (bucket: marketdata)
                                                              │
                              agent-service /klines  ◄────────┘
                                      │
                              agent-service /scan    ←── InfluxDB + Pipeline
                                      │
                                  前端展示
```

- **数据源**：Polygon.io REST API（免费版 5 req/min）
- **存储**：Amazon Timestream for InfluxDB，measurement `kline`，tag: `instrument` + `timeframe`
- **自动更新**：K8s CronJob `daily-ingest`，每天 UTC 01:00 自动拉取最新 K 线并执行信号扫描
- **手动更新**：前端设置页 → 单标的/全部 ingest

### 分析流程

```
前端 getKLines() ──► agent-service /klines/{instrument}  ←── InfluxDB
        │
        ▼
前端 analyzeInstrument() ──► agent-service /analyze  ──► 10层管道
        │
        ▼
    ChanChart 渲染: K线 + 笔 + 线段 + 中枢 + 买卖点 + MACD
```

---

## REST API

### Agent Service (Python FastAPI, port 8090)

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/health` | 健康检查 + InfluxDB 连接状态 |
| `GET` | `/klines/{instrument}?level=1d&limit=500` | 从 InfluxDB 获取 K 线 |
| `POST` | `/analyze` | 传入 K 线 → 运行 L0-L8 管道 → 返回完整结构分析 |
| `POST` | `/scan` | 传入标的列表 → 从 InfluxDB 获取数据 → 批量分析 |
| `POST` | `/ingest` | 从 Polygon.io 拉 K 线 → 写入 InfluxDB |
| `POST` | `/backtest` | 事件驱动回测 |

#### /analyze 返回结构

```json
{
  "instrument": "AAPL",
  "level": "1d",
  "kline_count": 151,
  "fractal_count": 68,
  "stroke_count": 10,
  "segment_count": 3,
  "center_count": 2,
  "divergence_count": 1,
  "signals": [{ "signal_type": "B1", "price": "252.30", "strength": "0.85", ... }],
  "fractals": [{ "type": "top", "timestamp": "...", "price": "...", "kline_index": 3 }],
  "strokes": [{ "direction": "up", "start_index": 0, "end_index": 5, "macd_area": "..." }],
  "segments": [{ "direction": "up", "stroke_count": 3, "termination_type": "first" }],
  "centers": [{ "zg": "260.50", "zd": "248.30", "gg": "265.00", "dd": "245.00" }],
  "divergences": [{ "type": "trend", "a_macd_area": "45.2", "c_macd_area": "38.1" }],
  "macd_values": [{ "dif": "1.23", "dea": "0.98", "histogram": "0.25" }],
  "trend": { "classification": "up_trend", "center_count": 2, "walk_state": "top_divergence" }
}
```

### Gateway 路由 (Spring Cloud Gateway, port 8080)

| Path Pattern | 目标服务 | 说明 |
|-------------|---------|------|
| `/api/agents/**` | agent-service:8090 | 缠论分析引擎（StripPrefix=2） |
| `/api/signals/**` | signal-service:8081 | Java 信号服务 |
| `/api/backtest/**` | backtest-service:8082 | 回测服务 |
| `/api/data/**` | data-service:8083 | 标的管理（instrument CRUD） |
| `/api/users/**` | user-service:8084 | 认证 + 自选股 |
| `/api/notifications/**` | notification-service:8085 | 通知推送 |

---

## 项目结构

```
zenalpha/
├── frontend/                          # React 18 SPA
│   ├── src/
│   │   ├── pages/                     # 态势总览, 区间套, 缠论图表, 持仓, 回顾, 回测, 设置
│   │   ├── components/
│   │   │   ├── chart/ChanChart.tsx    # 核心图表组件 (6层叠加 + MACD子图)
│   │   │   └── layout/               # AppLayout, Sidebar
│   │   ├── stores/                    # Zustand (auth, watchlist)
│   │   ├── api/                       # agent.ts, data.ts, auth.ts, http.ts
│   │   ├── lib/                       # cn.ts, chan-labels.ts (术语映射)
│   │   └── types/                     # chan.ts, api.ts
│   └── tailwind.config.ts
│
├── chanquant/                         # Python 缠论核心库
│   ├── core/
│   │   ├── objects.py                 # 不可变数据类: RawKLine, Fractal, Stroke, Segment, Center...
│   │   ├── pipeline.py                # AnalysisPipeline (L0-L8 串联)
│   │   ├── kline.py                   # L0 包含关系处理
│   │   ├── fractal.py                 # L1 分型识别
│   │   ├── stroke.py                  # L2 笔的划分
│   │   ├── segment.py                 # L3 线段划分
│   │   ├── center.py                  # L4 中枢识别
│   │   ├── trend.py                   # L5 趋势分类
│   │   ├── divergence.py              # L6 背驰判断
│   │   ├── signal.py                  # L7 买卖点生成
│   │   └── macd.py                    # MACD 增量计算
│   ├── api/
│   │   └── gateway.py                 # FastAPI 网关 (8 endpoints)
│   ├── data/
│   │   ├── timestream.py              # InfluxDB 客户端 (读写 K 线)
│   │   └── polygon.py                 # Polygon.io 客户端
│   └── backtest/
│       └── engine.py                  # 事件驱动回测引擎
│
├── services/                          # Java 微服务 (Maven multi-module)
│   ├── pom.xml                        # Parent POM
│   ├── common/                        # 共享: Enum + Record + DTO + Exception
│   ├── eureka-server/                 # 服务注册中心 (port 8761)
│   ├── gateway/                       # API 网关 + JWT (port 8080)
│   ├── signal-service/                # 信号服务 (port 8081)
│   ├── backtest-service/              # 回测服务 (port 8082)
│   ├── data-service/                  # 标的管理 (port 8083, K线已迁至InfluxDB)
│   ├── user-service/                  # JWT 认证 + Watchlist (port 8084)
│   └── notification-service/          # 邮件 + Webhook 通知 (port 8085)
│
├── terraform/                         # AWS IaC
│   ├── main.tf                        # 入口
│   ├── modules/
│   │   ├── vpc/                       # 3 AZ, public/private subnets, NAT
│   │   ├── eks/                       # EKS 1.29 + managed node group
│   │   ├── rds/                       # MySQL 8.0
│   │   ├── timestream/                # Amazon Timestream for InfluxDB
│   │   ├── ecr/                       # 容器镜像仓库
│   │   └── frontend/                  # S3 + CloudFront (OAC) + WAF
│   └── k8s/                           # Kubernetes 部署清单
│       ├── agent-service/             # Deployment + CronJob (daily-ingest)
│       ├── gateway/                   # Deployment + ConfigMap + Service
│       ├── eureka/                    # StatefulSet
│       ├── apollo/                    # ConfigDB init + Deployments
│       └── ...                        # signal, backtest, data, user, notification
│
├── Dockerfile.agent                   # Python agent-service 多阶段构建
├── tests/                             # Python 单元测试
└── docs/
    └── algorithm.md                   # 算法规格 (10层详解 + 修正说明)
```

---

## MySQL 表结构

9 张表，跨 4 个服务：

| Service | Tables |
|---------|--------|
| data-service | `instrument` |
| signal-service | `signal_record` |
| backtest-service | `backtest_result`, `trade` |
| user-service | `users`, `watchlists`, `watchlist_instruments` |
| notification-service | `notification_configs`, `notification_logs` |

> K 线数据已迁移至 InfluxDB，不再存储在 MySQL。

---

## AWS 基础设施

| 资源 | 规格 |
|------|------|
| VPC | 3 AZ, 6 subnets (3 public + 3 private), 1 NAT GW |
| EKS | Kubernetes 1.29, t3.medium × 3 node group |
| RDS | MySQL 8.0, db.t3.medium, private subnet |
| Timestream for InfluxDB | InfluxDB v2, bucket `marketdata`, org `zenalpha` |
| CloudFront | S3 origin (OAC) + NLB origin, WAF 附加, SPA routing |
| ECR | 容器镜像仓库 |
| NLB | Gateway 入口 (Kubernetes LoadBalancer Service) |

Region: `us-west-2`

---

## 快速开始

### 本地开发

```bash
git clone https://github.com/JasonJinzexuan/zenalpha.git
cd zenalpha

# 前端 — 需要 Node 20+
cd frontend
npm install
npm run dev         # http://localhost:3000

# Java 微服务 — 需要 JDK 17 + Maven 3.9+
cd ../services
mvn clean package -DskipTests

# Python 缠论引擎 — 需要 Python 3.12+
cd ..
pip install -e ".[api]"
uvicorn chanquant.api.gateway:app --port 8090
```

### 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `INFLUXDB_URL` | InfluxDB 地址 | `https://xxx.timestream-influxdb.us-west-2.on.aws:8086` |
| `INFLUXDB_TOKEN` | InfluxDB 访问 Token | `xxx` |
| `POLYGON_API_KEY` | Polygon.io API Key | `xxx` |
| `MYSQL_PASSWORD` | RDS MySQL 密码 | `xxx` |

### 一键部署（AWS）

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# 编辑 terraform.tfvars

terraform init && terraform apply
# K8s 部署清单在 terraform/k8s/
```

---

## 设计原则

| 原则 | 实现 |
|------|------|
| **BigDecimal 精度** | 所有价格/金融数值用 `BigDecimal` (Python `Decimal`)，核心算法无 `float` |
| **不可变数据** | Python `@dataclass(frozen=True)` + `NamedTuple`；Java `record` + `List.of()` |
| **微服务隔离** | 每服务独立部署、独立扩缩，agent-service 独立 Python 运行时 |
| **原文可追溯** | 每个信号附带 `source_lesson` 字段，映射缠论原文课号 |
| **IaC** | 全部基础设施 Terraform 管理 |
| **时序分离** | K 线数据存 InfluxDB（高效查询），业务数据存 MySQL |
| **中文化** | 缠论术语全中文显示（一买/二买/笔/线段/中枢/背驰） |

---

## 开发路线

| Phase | 内容 | 状态 |
|-------|------|------|
| **0+1** | 10 层算法管道 + 回测引擎 + Python CLI | ✅ Done |
| **2** | Java 微服务 + Terraform + K8s | ✅ Done |
| **3** | React 前端重写 + InfluxDB 时序存储 + agent-service | ✅ Done |
| 4 | LLM Agent 编排 (LangGraph + Bedrock) | Planned |
| 5 | 加密货币扩展 (Binance WebSocket) | Planned |
| 6 | 实时信号推送 (WebSocket + SNS) | Planned |

---

## 代码统计

| 模块 | 文件数 | 代码行数 |
|------|--------|----------|
| chanquant/ (Python) | 79 | ~7,000 |
| frontend/ (React+TS) | 24 | ~3,000 |
| services/ (Java) | 202 | ~6,000 |
| terraform/ (HCL) | 50 | ~1,700 |
| k8s/ (YAML) | 46 | ~1,050 |
| **Total** | **~401** | **~18,750** |

## License

Private. All rights reserved.
