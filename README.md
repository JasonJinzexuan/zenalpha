# ZenAlpha

基于缠论（缠中说禅技术分析理论）的量化信号识别平台。从原始 K 线出发，经过 10 层确定性算法管道，输出可追溯的买卖点信号。

## 定位

- **信号识别器**：自动执行 L0-L9 分析，输出 B1/B2/B3/S1/S2/S3 买卖信号
- **标的过滤器**：多标的扫描 → 评分排序 → Top N 输出
- **回测引擎**：事件驱动回测 + Walk-forward + Monte Carlo 验证

**不是**投资助手、不是交易系统、不接交易所 API。

---

## 架构

```
                    ┌──────────────────────────────────┐
                    │         CloudFront + S3           │
                    │      Vue 3 SPA (前端)             │
                    └──────────────┬───────────────────┘
                                   │ HTTPS
                    ┌──────────────▼───────────────────┐
                    │      Spring Cloud Gateway         │
                    │    (JWT 验证 + 路由 + CORS)       │
                    │         port 8080                 │
                    └──┬────┬────┬────┬────┬───────────┘
                       │    │    │    │    │
          ┌────────────▼┐ ┌▼────▼┐ ┌▼────▼──┐ ┌────────▼─┐
          │   signal    │ │back- │ │ data   │ │  user    │
          │   service   │ │test  │ │service │ │ service  │
          │  (L0-L9)   │ │svc   │ │        │ │ (JWT)    │
          │  port 8081  │ │8082  │ │ 8083   │ │  8084    │
          └──────┬──────┘ └──┬───┘ └───┬────┘ └────┬─────┘
                 │           │         │            │
          ┌──────▼───────────▼─────────▼────────────▼─────┐
          │                 RDS MySQL 8.0                  │
          └───────────────────────────────────────────────┘

     Eureka (服务注册)        Apollo (配置中心)       notification-service (8085)
```

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Lightweight Charts |
| API 网关 | Spring Cloud Gateway + JWT |
| 微服务 | Spring Boot 3.2 + Spring Cloud 2023 (Java 17) |
| 注册中心 | Eureka Server |
| 配置中心 | Apollo Config |
| 数据库 | RDS MySQL 8.0 |
| 容器编排 | EKS (Kubernetes 1.29) |
| 前端部署 | CloudFront + S3 (OAC) |
| IaC | Terraform 1.7+ |

---

## 快速开始

### 本地开发

```bash
git clone https://github.com/JasonJinzexuan/zenalpha.git
cd zenalpha

# 后端 — 需要 JDK 17 + Maven 3.9+
cd services
mvn clean package -DskipTests

# 前端 — 需要 Node 20+
cd ../frontend
npm install
npm run dev         # http://localhost:3000
```

### Python CLI（Phase 0+1 遗留）

```bash
uv sync
uv run zenalpha analyze AAPL --data data/aapl_daily.json
uv run zenalpha backtest AAPL --data data/aapl_daily.json --start 2021-01-01 --end 2026-01-01
```

### 一键部署（AWS）

```bash
# 1. 配置 Terraform
cd terraform
cp terraform.tfvars.example terraform.tfvars
# 编辑 terraform.tfvars 填入 DB 密码等

# 2. 一键部署
../scripts/deploy.sh
```

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
│  L7  买卖点生成      SignalGenerator       B1/S1 + B2/S2 + B3/S3 │
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
| 4 | L7 | B2 补充盘整背驰 + 小转大两个触发条件 | 第 053 课 |
| 5 | L8 | 替换加权评分为区间套递进定位 | 第 030 课 |

---

## 项目结构

```
zenalpha/
├── frontend/                          # Vue 3 SPA
│   ├── src/
│   │   ├── views/                     # Dashboard, Analysis, Scanner, Backtest, Settings
│   │   ├── components/                # KLineChart, SignalTable, MetricsCard, CenterOverlay
│   │   ├── stores/                    # Pinia (signal, backtest, user)
│   │   ├── api/                       # Axios clients
│   │   └── types/                     # TypeScript 类型定义
│   └── Dockerfile
│
├── services/                          # Java 微服务 (Maven multi-module)
│   ├── pom.xml                        # Parent POM (Spring Boot 3.2 + Spring Cloud 2023)
│   ├── common/                        # 共享: 8 Enum + 16 Record + DTO + Exception
│   ├── eureka-server/                 # 服务注册中心 (port 8761)
│   ├── gateway/                       # API 网关 + JWT 验证 (port 8080)
│   ├── signal-service/                # 核心: 10层算法引擎 + 评分 (port 8081)
│   │   └── engine/                    # MACDCalculator → ... → AnalysisPipeline
│   ├── backtest-service/              # 回测引擎 + 风控 (port 8082)
│   ├── data-service/                  # 行情数据 + Polygon.io (port 8083)
│   ├── user-service/                  # JWT 认证 + Watchlist (port 8084)
│   └── notification-service/          # 邮件 + Webhook 通知 (port 8085)
│
├── terraform/                         # AWS IaC
│   ├── modules/
│   │   ├── vpc/                       # 3 AZ, public/private subnets, NAT
│   │   ├── eks/                       # EKS 1.29 + managed node group
│   │   ├── rds/                       # MySQL 8.0
│   │   ├── ecr/                       # 8 个容器镜像仓库
│   │   ├── frontend/                  # S3 + CloudFront (OAC)
│   │   └── alb/                       # Application Load Balancer
│   └── k8s/                           # Kubernetes 部署清单
│       ├── eureka/                    # StatefulSet
│       ├── apollo/                    # ConfigDB init + Deployments
│       ├── gateway/                   # Deployment + LoadBalancer Service
│       ├── signal-service/            # Deployment + HPA (2-5 pods)
│       ├── data-service/              # Deployment + HPA (2-4 pods)
│       └── ...                        # backtest, user, notification
│
├── scripts/
│   ├── init-db.sql                    # MySQL 10 张表 DDL
│   ├── build-all.sh                   # 构建全部 Docker 镜像 + 推送 ECR
│   └── deploy.sh                      # Terraform apply + K8s deploy
│
├── chanquant/                         # Python CLI (Phase 0+1, 保留)
├── tests/                             # Python 单元测试
└── docs/
    └── algorithm.md                   # 算法规格 (10层详解 + 修正说明)
```

---

## REST API

### Gateway 路由

| Path | Service | 说明 |
|------|---------|------|
| `POST /api/signals/analyze` | signal-service | 单标的缠论分析 |
| `POST /api/signals/scan` | signal-service | 全市场扫描排序 |
| `POST /api/backtest/run` | backtest-service | 运行回测 |
| `GET /api/data/klines/{symbol}` | data-service | 获取 K 线数据 |
| `POST /api/data/klines/sync` | data-service | 从 Polygon.io 同步 |
| `GET /api/data/instruments` | data-service | 标的列表 |
| `POST /api/users/register` | user-service | 用户注册 |
| `POST /api/users/login` | user-service | 登录 (返回 JWT) |
| `GET /api/users/watchlists` | user-service | 自选股列表 |
| `POST /api/notifications/config` | notification-service | 通知配置 |

---

## 前端页面

| 页面 | 功能 |
|------|------|
| **Dashboard** | 信号概览面板：Top 信号表格 + 买/卖统计 + 平均评分 |
| **Analysis** | 单标的分析：K 线图 (Lightweight Charts) + 笔/线段/中枢叠加 + 信号标注 |
| **Scanner** | 全市场扫描：预设标的组 + 过滤器 + 评分排序 |
| **Backtest** | 回测界面：配置表单 + 指标卡片 (Sharpe/Sortino/MaxDD) + 交易日志 |
| **Settings** | 用户设置 + 通知配置 (邮件/Webhook) |

---

## MySQL 表结构

10 张表，跨 4 个服务：

| Service | Tables |
|---------|--------|
| data-service | `instrument`, `kline` |
| signal-service | `signal_record`, `scan_result` |
| backtest-service | `backtest_result`, `trade` |
| user-service | `user`, `watchlist` |
| notification-service | `notification_config`, `notification_log` |

初始化：`mysql -h <RDS_ENDPOINT> -u admin -p < scripts/init-db.sql`

---

## AWS 基础设施

Terraform 一键创建：

| 资源 | 规格 |
|------|------|
| VPC | 3 AZ, 6 subnets (3 public + 3 private), 1 NAT GW |
| EKS | Kubernetes 1.29, t3.medium × 3 node group |
| RDS | MySQL 8.0, db.t3.medium, private subnet |
| CloudFront | S3 origin (OAC), SPA routing, 24h cache |
| ECR | 8 repositories (每服务一个) |
| ALB | Gateway 入口, HTTP/HTTPS |

Region: `us-east-1`

---

## 设计原则

| 原则 | 实现 |
|------|------|
| **BigDecimal 精度** | 所有价格/金融数值用 `BigDecimal`，核心算法无 `float` |
| **不可变数据** | Java `record` + `List.of()`；Python `@dataclass(frozen=True)` |
| **微服务隔离** | 每服务独立数据库表、独立部署、独立扩缩 |
| **原文可追溯** | 每个信号附带 `sourceLesson` 字段，映射缠论原文课号 |
| **IaC** | 全部基础设施 Terraform 管理，零手动配置 |

---

## 开发路线

| Phase | 内容 | 状态 |
|-------|------|------|
| **0+1** | 10 层算法管道 + 回测引擎 + Python CLI | **Done** |
| **2** | Vue 前端 + Java 微服务 + Terraform + K8s | **Done** |
| 3 | LLM Agent 编排 (LangGraph + Bedrock) | Planned |
| 4 | 加密货币扩展 (Binance WebSocket) | Planned |
| 5 | 实时信号推送 (WebSocket + SNS) | Planned |

---

## 代码量

| 模块 | 文件数 | 代码行数 |
|------|--------|----------|
| services/ (Java) | 108 | ~6,400 |
| frontend/ (Vue+TS) | 20 | ~1,600 |
| terraform/ (HCL) | 22 | ~1,350 |
| k8s/ (YAML) | 22 | ~900 |
| chanquant/ (Python) | 15 | ~1,700 |
| scripts + SQL | 3 | ~400 |
| **Total** | **~210** | **~12,350** |

## License

Private. All rights reserved.
