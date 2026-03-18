# ZenAlpha 部署指南

> **最后更新**: 2026-03-18

---

## 目录

1. [前置条件](#1-前置条件)
2. [架构总览](#2-架构总览)
3. [快速开始（全新部署）](#3-快速开始全新部署)
4. [分步详解](#4-分步详解)
   - [4.1 Terraform — 基础设施](#41-terraform--基础设施)
   - [4.2 Karpenter — 自动扩缩容](#42-karpenter--自动扩缩容)
   - [4.3 构建并推送 Docker 镜像](#43-构建并推送-docker-镜像)
   - [4.4 部署 K8s 工作负载](#44-部署-k8s-工作负载)
   - [4.5 InfluxDB 初始化](#45-influxdb-初始化)
   - [4.6 Apollo 配置中心](#46-apollo-配置中心)
   - [4.7 前端部署](#47-前端部署)
5. [密钥管理](#5-密钥管理)
6. [日常运维](#6-日常运维)
7. [故障排查](#7-故障排查)
8. [成本优化](#8-成本优化)

---

## 1. 前置条件

| 工具 | 版本 | 用途 |
|------|------|------|
| AWS CLI | >= 2.x | AWS 资源管理 |
| Terraform | >= 1.5.0 | 基础设施即代码 |
| kubectl | >= 1.28 | K8s 集群管理 |
| Docker | >= 24.x | 容器镜像构建 |
| Maven | >= 3.9 | Java 服务构建 |
| Node.js | >= 18 | 前端构建 |
| Helm | >= 3.x | Karpenter 安装 |

**需要的 AWS 权限：**

部署用的 IAM 用户/角色需要以下服务权限：EKS、EC2、VPC、RDS、ECR、S3、CloudFront、WAF、Timestream InfluxDB、IAM。
建议：首次部署使用 `AdministratorAccess`，之后缩小权限范围。

---

## 2. 架构总览

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
│  │  托管节点组 (1x t3.medium)                                │    │
│  │    └── Karpenter 控制器                                   │    │
│  │                                                            │    │
│  │  Karpenter 节点 (Nx c7i.large, 自动扩缩)                 │    │
│  │    ├── Eureka (服务注册中心)                               │    │
│  │    ├── Apollo (配置中心: configservice+admin+portal)       │    │
│  │    ├── Gateway (Spring Cloud Gateway, JWT+CORS+路由)      │    │
│  │    ├── user-service (认证, JWT)                           │    │
│  │    ├── data-service (标的管理)                             │    │
│  │    ├── signal-service (缠论信号)                           │    │
│  │    ├── backtest-service (Walk-forward + Monte Carlo)      │    │
│  │    ├── notification-service (告警)                        │    │
│  │    └── agent-service (Python, 缠论引擎)                   │    │
│  │                                                            │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  RDS MySQL 8.0          Timestream InfluxDB v2                    │
│  (关系型数据)            (OHLCV K线时序数据)                       │
│                                                                    │
│  ECR (容器镜像仓库)                                               │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

外部依赖：Polygon.io（行情数据源）
```

**Terraform 模块：**

| 模块 | 创建的资源 |
|------|-----------|
| `vpc` | VPC、3 公有 + 3 私有子网、IGW、NAT GW、路由表 |
| `eks` | EKS 集群、托管节点组、OIDC Provider、IAM 角色、安全组 |
| `rds` | RDS MySQL 实例、子网组、安全组 |
| `ecr` | 所有服务的 ECR 镜像仓库 |
| `timestream` | Timestream InfluxDB 实例、安全组、IRSA IAM 角色 |
| `frontend` | S3 存储桶、CloudFront 分发、WAF (us-east-1)、OAC |
| `k8s.tf` | K8s 命名空间、Secrets（DB、JWT、agent、polygon）、ConfigMaps |

---

## 3. 快速开始（全新部署）

适合有经验的用户，一次性执行所有步骤。

```bash
# ---- 步骤 1: Terraform ----
cd terraform
cp terraform.tfvars.example terraform.tfvars   # 编辑配置
cat > secrets.auto.tfvars << 'EOF'
db_password        = "<生成强密码>"
influxdb_password  = "<生成强密码>"
influxdb_api_token = "<步骤5创建后填写>"          # 先占位
polygon_api_key    = "<你的 Polygon API Key>"
EOF

terraform init
terraform apply                                     # 约 20 分钟

# ---- 步骤 2: 配置 kubectl ----
aws eks update-kubeconfig --name zenalpha-prod-eks --region us-west-2

# ---- 步骤 3: 安装 Karpenter ----
# （完整命令见 4.2 节）
helm install karpenter oci://public.ecr.aws/karpenter/karpenter ...
kubectl apply -f karpenter-nodepool.yaml

# ---- 步骤 4: 构建并推送镜像 ----
export ECR_REGISTRY=$(terraform -chdir=terraform output -raw ecr_registry)
scripts/build-all.sh                                # 构建 + 推送到 ECR

# ---- 步骤 5: 部署 K8s ----
scripts/deploy-k8s.sh                               # 全量部署

# ---- 步骤 6: InfluxDB API Token ----
# （见 4.5 节 — 创建 token，更新 secrets.auto.tfvars，terraform apply）

# ---- 步骤 7: 前端 ----
cd frontend && npm ci && npm run build
aws s3 sync dist/ s3://zenalpha-prod-frontend --delete
aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"

# ---- 步骤 8: 更新 api_gateway_domain ----
# Gateway 服务获得 ALB 后，更新 terraform.tfvars：
kubectl get svc gateway -n zenalpha -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
# 将此值填入 terraform.tfvars → api_gateway_domain，然后：
terraform apply
```

---

## 4. 分步详解

### 4.1 Terraform — 基础设施

#### 4.1.1 配置变量

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

编辑 `terraform.tfvars`：

```hcl
project_name = "zenalpha"
environment  = "prod"
region       = "us-west-2"

# EKS — 托管节点组（只运行 Karpenter）
eks_node_instance_type = "t3.medium"
eks_node_count         = 1
eks_node_min           = 1
eks_node_max           = 1

# RDS
db_instance_class = "db.t3.micro"    # 生产环境升级到 db.r6g.large
db_name           = "zenalpha"
db_username       = "zenalpha_admin"
db_multi_az       = false             # 生产环境设为 true 实现高可用
db_storage_gb     = 20

# 域名（可选）
domain_name         = ""
acm_certificate_arn = ""
api_gateway_domain  = ""              # 首次部署后填写
```

#### 4.1.2 配置密钥

创建 `secrets.auto.tfvars`（已被 gitignore）：

```bash
cat > secrets.auto.tfvars << 'EOF'
# 请勿提交 — 已被 gitignore
db_password        = "$(openssl rand -base64 24)"
influxdb_password  = "$(openssl rand -base64 24)"
influxdb_api_token = "placeholder"    # InfluxDB 初始化后更新
polygon_api_key    = "你的 Polygon Key"
EOF
```

> **重要**：请生成真实密码。`influxdb_api_token` 先用占位符，在[步骤 4.5](#45-influxdb-初始化) 中创建真正的 token。

#### 4.1.3 执行

```bash
terraform init
terraform apply
```

预计耗时：约 20 分钟（RDS 和 InfluxDB 最慢）。

#### 4.1.4 配置 kubectl

```bash
# 此命令也在 terraform output 中
aws eks update-kubeconfig --name zenalpha-prod-eks --region us-west-2
kubectl get nodes   # 应看到 1 个 t3.medium 节点
```

### 4.2 Karpenter — 自动扩缩容

Karpenter 管理所有应用 pod 的工作节点（c7i.large）。托管节点组（1x t3.medium）仅运行 Karpenter 控制器本身。

#### 4.2.1 安装 Karpenter

```bash
CLUSTER_NAME="zenalpha-prod-eks"
CLUSTER_ENDPOINT=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.endpoint" --output text)
KARPENTER_VERSION="1.1.1"  # 检查最新版：https://github.com/aws/karpenter-provider-aws/releases

helm install karpenter oci://public.ecr.aws/karpenter/karpenter \
  --namespace kube-system \
  --set "settings.clusterName=$CLUSTER_NAME" \
  --set "settings.clusterEndpoint=$CLUSTER_ENDPOINT" \
  --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::<ACCOUNT_ID>:role/zenalpha-prod-karpenter-role" \
  --version "$KARPENTER_VERSION" \
  --wait
```

#### 4.2.2 创建节点池

```bash
kubectl apply -f - << 'EOF'
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  role: zenalpha-prod-eks-node-role
  amiSelectorTerms:
    - alias: al2@latest
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: zenalpha-prod-eks
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: zenalpha-prod-eks
  tags:
    Project: zenalpha
    Environment: prod
    karpenter.sh/discovery: zenalpha-prod-eks
---
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["c7i.large"]
      expireAfter: 720h
  limits:
    cpu: "16"
    memory: 64Gi
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 30m
EOF
```

> **为什么选 c7i.large？** 计算优化型，持续负载下性价比比 t3.medium 高约 30%，无突发积分问题。

> **为什么保留 1 个 t3.medium？** Karpenter 控制器有 `nodeAffinity: karpenter.sh/nodepool DoesNotExist`——不能运行在自己管理的节点上（防止自杀）。托管节点组提供这个安全港。

### 4.3 构建并推送 Docker 镜像

```bash
# 从 terraform 获取 ECR 地址
export ECR_REGISTRY=$(terraform -chdir=terraform output -raw ecr_registry)

# 构建所有服务并推送到 ECR
scripts/build-all.sh
```

此脚本执行：
- 用 Maven 构建所有 7 个 Java 服务（单一多模块构建）
- 构建 agent-service（Python）Docker 镜像
- 构建前端 Docker 镜像（S3 部署不用，但可备用）
- 标记并推送所有镜像到 ECR

**构建单个服务：**

```bash
cd services && mvn clean package -pl gateway -am -DskipTests
docker build -t $ECR_REGISTRY/zenalpha-gateway:latest -f services/gateway/Dockerfile services/
docker push $ECR_REGISTRY/zenalpha-gateway:latest
```

### 4.4 部署 K8s 工作负载

```bash
scripts/deploy-k8s.sh          # 全量部署
```

**部署顺序（自动处理）：**

```
1. namespace
2. eureka（服务注册中心——必须先于其他服务启动）
3. apollo（DB 初始化 Job → configservice → adminservice → portal）
4. gateway（Spring Cloud Gateway）
5. user-service, data-service, signal-service, backtest-service, notification-service
6. agent-service（Python FastAPI）
```

**选择性部署：**

```bash
scripts/deploy-k8s.sh gateway        # 只部署 gateway
scripts/deploy-k8s.sh apollo         # 只部署 apollo
scripts/deploy-k8s.sh user-service   # 只部署 user-service
```

**关键实现细节：**

- `envsubst '${ECR_REGISTRY}'`——只替换 ECR 地址，保留 K8s `$(VAR)` 变量引用不被破坏
- K8s 环境变量顺序：`DB_HOST` 必须定义在 JDBC URL 中 `$(DB_HOST)` **之前**
- Apollo 存活探针 `initialDelaySeconds: 120`——Spring Boot 启动 > 60s

### 4.5 InfluxDB 初始化

Terraform 创建 InfluxDB 实例后，需要创建 API Token。管理员**密码** ≠ API **Token**，这是两个不同的东西。

```bash
# 从集群内部执行（InfluxDB 在 VPC 内，外部无法直接访问）
INFLUX_HOST="<terraform output 中的 endpoint>"

# 步骤 1：用管理员密码登录获取 session cookie
# 步骤 2：创建 API token
kubectl run influx-setup --rm -it --restart=Never -n zenalpha \
  --image=curlimages/curl -- sh -c "
    curl -sk -c /tmp/cookie -X POST \
      https://${INFLUX_HOST}:8086/api/v2/signin \
      -u 'admin:<influxdb_password>' &&
    curl -sk -b /tmp/cookie -X POST \
      https://${INFLUX_HOST}:8086/api/v2/authorizations \
      -H 'Content-Type: application/json' \
      -d '{
        \"orgID\": \"<org-id>\",
        \"description\": \"agent-service\",
        \"permissions\": [
          {\"action\":\"read\", \"resource\":{\"type\":\"buckets\"}},
          {\"action\":\"write\",\"resource\":{\"type\":\"buckets\"}}
        ]
      }'
  "
```

> **如何获取 orgID：** 先登录（第一个 curl），再 `GET /api/v2/orgs` 列出组织。

复制响应中的 `token` 字段，然后：

```bash
# 更新 secrets.auto.tfvars
# influxdb_api_token = "<粘贴 token>"

terraform apply -target=kubernetes_secret.agent
kubectl rollout restart deployment/agent-service -n zenalpha
```

### 4.6 Apollo 配置中心

Apollo 由 `deploy-k8s.sh` 自动部署。DB 初始化 Job 会创建 `ApolloConfigDB` 和 `ApolloPortalDB` 的 schema。

**访问 Apollo Portal：**

```bash
kubectl port-forward svc/apollo-portal -n zenalpha 8070:8070
# 打开 http://localhost:8070（admin / DB 初始化中设置的默认密码）
```

**管理的应用：**

| App ID | 配置项 |
|--------|-------|
| gateway | CORS 源、Eureka、Gateway 路由、端口 |
| user-service | Eureka、JWT 过期时间、JPA/Hibernate |
| data-service | Eureka、JPA/Hibernate |
| signal-service | Eureka、JPA/Hibernate |
| notification-service | Eureka、JPA/Hibernate |
| backtest-service | Eureka、JPA/Hibernate |
| agent-service | InfluxDB 连接、Polygon 限速 |

> **注意**：敏感值（数据库密码、JWT 密钥、InfluxDB token、Polygon API key）**不在** Apollo 中，而是通过 Terraform 管理的 K8s Secrets 注入。

### 4.7 前端部署

前端是 React 18 SPA，通过 S3 + CloudFront 提供服务。

```bash
cd frontend
npm ci
npm run build

# 上传到 S3
aws s3 sync dist/ s3://zenalpha-prod-frontend --delete

# 清除 CloudFront 缓存
DIST_ID=$(terraform -chdir=terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

**CloudFront 路由：**

| 路径 | 源 | 说明 |
|------|-----|------|
| `/api/*` | ALB（K8s gateway） | API 请求代理到后端 |
| `/*` | S3 存储桶 | 静态前端资源 |

---

## 5. 密钥管理

### 密钥流转

```
secrets.auto.tfvars (已 gitignore)
        │
        ▼
    Terraform
        │
        ├──▶ kubernetes_secret "zenalpha-db-secret"   → DB 主机/用户/密码
        ├──▶ kubernetes_secret "zenalpha-secrets"      → JWT 密钥（自动生成）
        ├──▶ kubernetes_secret "agent-secrets"         → InfluxDB URL + API Token
        └──▶ kubernetes_secret "polygon-secret"        → Polygon API Key
                │
                ▼
         K8s Pod 环境变量 (通过 secretKeyRef 引用)
```

### 密钥存放位置

| 密钥 | 位置 | 说明 |
|------|------|------|
| `db_password` | `secrets.auto.tfvars` | RDS 主密码 |
| `influxdb_password` | `secrets.auto.tfvars` | InfluxDB 管理员登录密码 |
| `influxdb_api_token` | `secrets.auto.tfvars` | InfluxDB v2 API Token（≠密码） |
| `polygon_api_key` | `secrets.auto.tfvars` | Polygon.io 行情 API 密钥 |
| JWT 密钥 | 自动生成 | Terraform `random_password`，64 字符 |

### 安全检查清单

- [x] `secrets.auto.tfvars` 在 `.gitignore` 中
- [x] 源码中无硬编码密钥
- [x] JWT 密钥无默认回退值
- [x] CORS 限制为 CloudFront 域名 + localhost
- [x] RDS 连接使用 SSL（`useSSL=true&requireSSL=true`）
- [x] InfluxDB 使用 API Token 而非密码

---

## 6. 日常运维

### 更新单个服务

```bash
# 重新构建
cd services && mvn clean package -pl signal-service -am -DskipTests
docker build -t $ECR_REGISTRY/zenalpha-signal-service:latest -f services/signal-service/Dockerfile services/
docker push $ECR_REGISTRY/zenalpha-signal-service:latest

# 部署
scripts/deploy-k8s.sh signal-service
# 或者直接
kubectl rollout restart deployment/signal-service -n zenalpha
```

### 服务扩缩容

```bash
kubectl scale deployment/gateway -n zenalpha --replicas=3
# Karpenter 会自动扩容节点
```

### 查看日志

```bash
kubectl logs -f deployment/gateway -n zenalpha --tail=100
kubectl logs -f deployment/agent-service -n zenalpha --tail=100 | grep -v "GET /health"
```

### 检查 Eureka 注册表

```bash
kubectl port-forward svc/eureka-server -n zenalpha 8761:8761
curl -s http://localhost:8761/eureka/apps -H "Accept: application/json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for app in data['applications']['application']:
    instances = app.get('instance', [])
    if isinstance(instances, dict): instances = [instances]
    statuses = [i['status'] for i in instances]
    print(f\"{app['name']}: {statuses}\")
"
```

### 更新 Apollo 配置

```bash
kubectl port-forward svc/apollo-portal -n zenalpha 8070:8070
# 打开 http://localhost:8070，在 Web UI 中编辑配置，然后发布
```

### 轮换密钥

```bash
# 1. 更新 secrets.auto.tfvars 中的密钥值
# 2. 执行
terraform apply -target=kubernetes_secret.db -target=kubernetes_secret.agent
# 3. 重启相关服务
kubectl rollout restart deployment -n zenalpha
```

### 同步行情数据

```bash
# 一次性同步
python3 scripts/sync_polygon.py --symbols AAPL,TSLA,NVDA --days 365

# 每日同步的 CronJob 已自动部署
kubectl get cronjob -n zenalpha
```

---

## 7. 故障排查

### Pod 一直 Pending

```bash
kubectl describe pod <pod-name> -n zenalpha | tail -10
```

**常见原因：**

| 现象 | 原因 | 修复 |
|------|------|------|
| `Insufficient cpu/memory` | 节点资源满 | 检查 Karpenter NodePool 限制，增加 `cpu`/`memory` 上限 |
| `SubnetsNotFound` | 缺少 `karpenter.sh/discovery` 标签 | 执行 `terraform apply` 恢复标签 |
| `node affinity` | 调度到错误节点类型 | 检查 pod 的 nodeSelector/affinity |

### Eureka 注册表为空

节点迁移后，服务可能丢失注册。

```bash
kubectl rollout restart deployment -n zenalpha    # 全部重启
```

### Agent-service InfluxDB 错误

| 错误 | 原因 | 修复 |
|------|------|------|
| `ConnectTimeoutError port=80` | URL 缺少 `https://` 和 `:8086` | 修复 `k8s.tf` 中的 `influxdb-url`，`terraform apply` |
| `401 Unauthorized` | 用了密码而非 API Token | 创建 API Token（4.5 节），更新 secret |
| `404 bucket not found` | Bucket 未创建 | 通过 InfluxDB UI 或 API 创建 |

### Apollo 崩溃循环（CrashLoopBackOff）

| 错误 | 原因 | 修复 |
|------|------|------|
| `Table 'ApolloConfigDB.ServerConfig' doesn't exist` | 数据库未初始化 | 执行 `deploy-k8s.sh apollo`（会运行初始化 Job） |
| `UnknownHostException: $(DB_HOST)` | 环境变量顺序错误 | `DB_HOST` 必须在 YAML 中定义在 `$(DB_HOST)` 之前 |
| 被存活探针杀死 | `initialDelaySeconds` 太低 | Spring Boot 设为 120+ |

### K8s 环境变量 `$(VAR)` 未解析

如果日志中看到字面量 `$(DB_HOST)`，两种可能原因：

1. **envsubst 破坏**——不限制范围的 `envsubst` 会替换所有变量。修复：`envsubst '${ECR_REGISTRY}'`
2. **声明顺序**——被引用的变量必须在 env 列表中声明在引用之前

---

## 8. 成本优化

### 当前生产成本估算

| 资源 | 规格 | 月费用（估算） |
|------|------|---------------|
| EKS 集群 | 控制面板 | $73 |
| 托管节点组 | 1x t3.medium（仅 Karpenter） | ~$30 |
| Karpenter 节点 | 2-3x c7i.large（自动扩缩） | ~$120-180 |
| RDS MySQL | db.t3.micro, 单 AZ, 20GB | ~$15 |
| Timestream InfluxDB | db.influx.medium | ~$64 |
| NAT Gateway | 单个，共享 | ~$32 + 数据传输 |
| CloudFront | 标准版，含 WAF | ~$5-20（取决于流量） |
| ECR | ~2GB 镜像 | ~$1 |
| **合计** | | **~$340-415/月** |

### 省钱技巧

- **单 NAT Gateway**——已实施。多 AZ NAT 费用为 3 倍。
- **Karpenter `WhenEmpty` 合并策略**——30 分钟后移除空闲节点。
- **RDS 单 AZ**——开发/测试可以，生产环境开启 Multi-AZ。
- **Spot 实例**——在 NodePool 的 `capacity-type` 中添加 `spot` 用于非关键负载。

---

## 文件参考

```
zenalpha/
├── terraform/
│   ├── main.tf                    # 模块组合
│   ├── variables.tf               # 输入变量
│   ├── outputs.tf                 # 输出值
│   ├── versions.tf                # Provider 版本
│   ├── k8s.tf                     # K8s 命名空间、Secrets、ConfigMaps
│   ├── terraform.tfvars           # 非敏感配置（提交到 git）
│   ├── secrets.auto.tfvars        # 密钥（不提交，gitignored）
│   ├── modules/
│   │   ├── vpc/                   # VPC、子网、NAT
│   │   ├── eks/                   # EKS 集群、节点组、OIDC
│   │   ├── rds/                   # MySQL 实例
│   │   ├── ecr/                   # 容器镜像仓库
│   │   ├── timestream/            # InfluxDB 实例
│   │   └── frontend/              # S3 + CloudFront + WAF
│   └── k8s/                       # K8s YAML 清单
│       ├── namespace.yaml
│       ├── eureka/                # StatefulSet + Service
│       ├── apollo/                # DB 初始化 Job + 3 个 Deployment + Service
│       ├── gateway/               # Deployment + LoadBalancer Service
│       ├── user-service/          # Deployment + Service
│       ├── data-service/
│       ├── signal-service/
│       ├── backtest-service/
│       ├── notification-service/
│       └── agent-service/         # Deployment + CronJob
├── scripts/
│   ├── build-all.sh               # 构建所有镜像 + 推送到 ECR
│   ├── deploy-k8s.sh              # 部署所有 K8s 资源
│   └── sync_polygon.py            # 行情数据同步脚本
├── services/                      # Java 微服务 (Spring Boot)
├── chanquant/                     # Python 缠论引擎
└── frontend/                      # React 18 + TypeScript + Tailwind
```
