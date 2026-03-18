# ZenAlpha Deployment Guide / 部署指南

> **Last updated / 最后更新**: 2026-03-18

---

## Table of Contents / 目录

1. [Prerequisites / 前置条件](#1-prerequisites--前置条件)
2. [Architecture Overview / 架构总览](#2-architecture-overview--架构总览)
3. [Quick Start (Fresh Deploy) / 快速开始（全新部署）](#3-quick-start-fresh-deploy--快速开始全新部署)
4. [Step-by-Step Guide / 分步详解](#4-step-by-step-guide--分步详解)
   - [4.1 Terraform — Infrastructure / 基础设施](#41-terraform--infrastructure--基础设施)
   - [4.2 Karpenter — Auto Scaling / 自动扩缩容](#42-karpenter--auto-scaling--自动扩缩容)
   - [4.3 Build & Push Docker Images / 构建并推送镜像](#43-build--push-docker-images--构建并推送镜像)
   - [4.4 Deploy K8s Workloads / 部署 K8s 工作负载](#44-deploy-k8s-workloads--部署-k8s-工作负载)
   - [4.5 InfluxDB Setup / InfluxDB 初始化](#45-influxdb-setup--influxdb-初始化)
   - [4.6 Apollo Configuration Center / Apollo 配置中心](#46-apollo-configuration-center--apollo-配置中心)
   - [4.7 Frontend Deployment / 前端部署](#47-frontend-deployment--前端部署)
5. [Secret Management / 密钥管理](#5-secret-management--密钥管理)
6. [Day-2 Operations / 日常运维](#6-day-2-operations--日常运维)
7. [Troubleshooting / 故障排查](#7-troubleshooting--故障排查)
8. [Cost Optimization / 成本优化](#8-cost-optimization--成本优化)

---

## 1. Prerequisites / 前置条件

| Tool / 工具 | Version / 版本 | Purpose / 用途 |
|-------------|----------------|----------------|
| AWS CLI | >= 2.x | AWS resource management / AWS 资源管理 |
| Terraform | >= 1.5.0 | Infrastructure as Code / 基础设施即代码 |
| kubectl | >= 1.28 | K8s cluster management / K8s 集群管理 |
| Docker | >= 24.x | Container image build / 容器镜像构建 |
| Maven | >= 3.9 | Java service build / Java 服务构建 |
| Node.js | >= 18 | Frontend build / 前端构建 |
| Helm | >= 3.x | Karpenter installation / Karpenter 安装 |

**AWS permissions required / 需要的 AWS 权限:**

The deploying IAM user/role needs permissions for: EKS, EC2, VPC, RDS, ECR, S3, CloudFront, WAF, Timestream InfluxDB, IAM.
Recommended: use `AdministratorAccess` for initial setup, then scope down.

部署用的 IAM 用户/角色需要以下权限：EKS、EC2、VPC、RDS、ECR、S3、CloudFront、WAF、Timestream InfluxDB、IAM。
建议：首次部署使用 `AdministratorAccess`，之后缩小权限范围。

---

## 2. Architecture Overview / 架构总览

```
┌──────────────── AWS Cloud ────────────────────────────────────────┐
│                                                                    │
│  CloudFront + WAF ──── S3 (React SPA)                             │
│       │                                                            │
│       │ /api/*                                                     │
│       ▼                                                            │
│  ALB (K8s LoadBalancer Service)                                    │
│       │                                                            │
│  ┌────▼──── EKS Cluster ─────────────────────────────────────┐    │
│  │                                                            │    │
│  │  Managed Node Group (1x t3.medium)                        │    │
│  │    └── Karpenter controller                               │    │
│  │                                                            │    │
│  │  Karpenter Nodes (Nx c7i.large, auto-scaled)              │    │
│  │    ├── Eureka (service registry)                          │    │
│  │    ├── Apollo (config center: configservice+admin+portal) │    │
│  │    ├── Gateway (Spring Cloud Gateway, JWT+CORS+routing)   │    │
│  │    ├── user-service (auth, JWT)                           │    │
│  │    ├── data-service (instrument CRUD)                     │    │
│  │    ├── signal-service (Chan Theory signals)               │    │
│  │    ├── backtest-service (walk-forward + Monte Carlo)      │    │
│  │    ├── notification-service (alerts)                      │    │
│  │    └── agent-service (Python, Chan Theory engine)         │    │
│  │                                                            │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  RDS MySQL 8.0          Timestream InfluxDB v2                    │
│  (relational data)      (OHLCV K-line time-series)                │
│                                                                    │
│  ECR (container registry)                                         │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

External:  Polygon.io (market data source / 行情数据源)
```

**Terraform modules / Terraform 模块:**

| Module | Resources Created / 创建的资源 |
|--------|-------------------------------|
| `vpc` | VPC, 3 public + 3 private subnets, IGW, NAT GW, route tables |
| `eks` | EKS cluster, managed node group, OIDC provider, IAM roles, security groups |
| `rds` | RDS MySQL instance, subnet group, security group |
| `ecr` | ECR repositories for all services |
| `timestream` | Timestream InfluxDB instance, security group, IAM role for IRSA |
| `frontend` | S3 bucket, CloudFront distribution, WAF (us-east-1), OAC |
| `k8s.tf` | K8s namespace, secrets (DB, JWT, agent, polygon), configmaps |

---

## 3. Quick Start (Fresh Deploy) / 快速开始（全新部署）

For experienced users — the complete sequence in one block.
适合有经验的用户 — 一次性执行所有步骤。

```bash
# ---- Step 1: Terraform ----
cd terraform
cp terraform.tfvars.example terraform.tfvars   # Edit values / 编辑配置
cat > secrets.auto.tfvars << 'EOF'
db_password        = "<generate-strong-password>"
influxdb_password  = "<generate-strong-password>"
influxdb_api_token = "<created-after-step-5>"      # Placeholder first / 先占位
polygon_api_key    = "<your-polygon-api-key>"
EOF

terraform init
terraform apply                                     # ~20 min

# ---- Step 2: Configure kubectl ----
aws eks update-kubeconfig --name zenalpha-prod-eks --region us-west-2

# ---- Step 3: Install Karpenter ----
# (see section 4.2 for full commands)
helm install karpenter oci://public.ecr.aws/karpenter/karpenter ...
kubectl apply -f karpenter-nodepool.yaml

# ---- Step 4: Build & Push ----
export ECR_REGISTRY=$(terraform -chdir=terraform output -raw ecr_registry)
scripts/build-all.sh                                # Builds + pushes to ECR

# ---- Step 5: Deploy K8s ----
scripts/deploy-k8s.sh                               # Full deploy

# ---- Step 6: InfluxDB API Token ----
# (see section 4.5 — create token, update secrets.auto.tfvars, terraform apply)

# ---- Step 7: Frontend ----
cd frontend && npm ci && npm run build
aws s3 sync dist/ s3://zenalpha-prod-frontend --delete
aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"

# ---- Step 8: Update api_gateway_domain ----
# After gateway service gets an ALB, update terraform.tfvars:
kubectl get svc gateway -n zenalpha -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
# Put this value in terraform.tfvars → api_gateway_domain, then:
terraform apply
```

---

## 4. Step-by-Step Guide / 分步详解

### 4.1 Terraform — Infrastructure / 基础设施

#### 4.1.1 Configure Variables / 配置变量

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
编辑 `terraform.tfvars`：

```hcl
project_name = "zenalpha"
environment  = "prod"
region       = "us-west-2"

# EKS — Managed Node Group (runs Karpenter only)
# EKS — 托管节点组（只运行 Karpenter）
eks_node_instance_type = "t3.medium"
eks_node_count         = 1
eks_node_min           = 1
eks_node_max           = 1

# RDS
db_instance_class = "db.t3.micro"    # Upgrade to db.r6g.large for production / 生产环境升级
db_name           = "zenalpha"
db_username       = "zenalpha_admin"
db_multi_az       = false             # Set true for production HA / 生产环境设为 true
db_storage_gb     = 20

# Domain (optional / 可选)
domain_name         = ""
acm_certificate_arn = ""
api_gateway_domain  = ""              # Fill after first deploy / 首次部署后填写
```

#### 4.1.2 Configure Secrets / 配置密钥

Create `secrets.auto.tfvars` (gitignored):
创建 `secrets.auto.tfvars`（已被 gitignore）：

```bash
cat > secrets.auto.tfvars << 'EOF'
# DO NOT COMMIT — gitignored
db_password        = "$(openssl rand -base64 24)"
influxdb_password  = "$(openssl rand -base64 24)"
influxdb_api_token = "placeholder"    # Will be updated after InfluxDB init / InfluxDB 初始化后更新
polygon_api_key    = "your-polygon-key-here"
EOF
```

> **Important / 重要**: Generate real passwords. `influxdb_api_token` is a placeholder — you'll create a real one in [step 4.5](#45-influxdb-setup--influxdb-初始化).
>
> 请生成真实密码。`influxdb_api_token` 先用占位符，在 [步骤 4.5](#45-influxdb-setup--influxdb-初始化) 中创建真正的 token。

#### 4.1.3 Apply / 执行

```bash
terraform init
terraform apply
```

Expected time: ~20 minutes (RDS and InfluxDB take the longest).
预计耗时：约 20 分钟（RDS 和 InfluxDB 最慢）。

#### 4.1.4 Configure kubectl

```bash
# Command is also in terraform output / 命令也在 terraform output 中
aws eks update-kubeconfig --name zenalpha-prod-eks --region us-west-2
kubectl get nodes   # Should see 1 t3.medium node / 应看到 1 个 t3.medium 节点
```

### 4.2 Karpenter — Auto Scaling / 自动扩缩容

Karpenter manages worker nodes (c7i.large) for all application pods. The managed node group (1x t3.medium) only runs the Karpenter controller itself.

Karpenter 管理所有应用 pod 的工作节点（c7i.large）。托管节点组（1x t3.medium）仅运行 Karpenter 控制器本身。

#### 4.2.1 Install Karpenter / 安装 Karpenter

```bash
# Get cluster info / 获取集群信息
CLUSTER_NAME="zenalpha-prod-eks"
CLUSTER_ENDPOINT=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.endpoint" --output text)
KARPENTER_VERSION="1.1.1"  # Check latest: https://github.com/aws/karpenter-provider-aws/releases

# Install via Helm
helm install karpenter oci://public.ecr.aws/karpenter/karpenter \
  --namespace kube-system \
  --set "settings.clusterName=$CLUSTER_NAME" \
  --set "settings.clusterEndpoint=$CLUSTER_ENDPOINT" \
  --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::<ACCOUNT_ID>:role/zenalpha-prod-karpenter-role" \
  --version "$KARPENTER_VERSION" \
  --wait
```

#### 4.2.2 Create NodePool + EC2NodeClass / 创建节点池

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

> **Why c7i.large? / 为什么选 c7i.large?** Compute-optimized, ~30% better price-performance than t3.medium for sustained workloads. No burstable credit surprises.
>
> 计算优化型，持续负载下性价比比 t3.medium 高约 30%，无突发积分问题。

> **Why keep 1x t3.medium? / 为什么保留 1 个 t3.medium?** Karpenter controller has `nodeAffinity: karpenter.sh/nodepool DoesNotExist` — it cannot run on nodes it manages (to prevent self-eviction). The managed node group provides this safe harbor.
>
> Karpenter 控制器有 `nodeAffinity: karpenter.sh/nodepool DoesNotExist` — 不能运行在自己管理的节点上（防止自杀）。托管节点组提供这个安全港。

### 4.3 Build & Push Docker Images / 构建并推送镜像

```bash
# Get ECR registry from terraform / 从 terraform 获取 ECR 地址
export ECR_REGISTRY=$(terraform -chdir=terraform output -raw ecr_registry)

# Build all services + push to ECR / 构建所有服务并推送
scripts/build-all.sh
```

This script:
- Builds all 7 Java services with Maven (single multi-module build)
- Builds the agent-service (Python) Docker image
- Builds the frontend Docker image (not used in S3 deploy, but available)
- Tags and pushes all images to ECR

此脚本：
- 用 Maven 构建所有 7 个 Java 服务（单一多模块构建）
- 构建 agent-service（Python）Docker 镜像
- 构建前端 Docker 镜像（S3 部署不用，但可备用）
- 标记并推送所有镜像到 ECR

**To build a single service / 构建单个服务：**

```bash
cd services && mvn clean package -pl gateway -am -DskipTests
docker build -t $ECR_REGISTRY/zenalpha-gateway:latest -f services/gateway/Dockerfile services/
docker push $ECR_REGISTRY/zenalpha-gateway:latest
```

### 4.4 Deploy K8s Workloads / 部署 K8s 工作负载

```bash
scripts/deploy-k8s.sh          # Full deploy / 全量部署
```

**Deployment order (handled automatically) / 部署顺序（自动处理）：**

```
1. namespace
2. eureka (service registry — must be up before other services)
3. apollo (DB init job → configservice → adminservice → portal)
4. gateway (Spring Cloud Gateway)
5. user-service, data-service, signal-service, backtest-service, notification-service
6. agent-service (Python FastAPI)
```

**Selective deploy / 选择性部署：**

```bash
scripts/deploy-k8s.sh gateway        # Only gateway / 只部署 gateway
scripts/deploy-k8s.sh apollo         # Only apollo / 只部署 apollo
scripts/deploy-k8s.sh user-service   # Only user-service / 只部署 user-service
```

**Key implementation details / 关键实现细节：**

- `envsubst '${ECR_REGISTRY}'` — only substitutes ECR registry, leaves K8s `$(VAR)` references intact
- `envsubst '${ECR_REGISTRY}'` — 只替换 ECR 地址，保留 K8s `$(VAR)` 变量引用不被破坏
- K8s env var ordering: `DB_HOST` must be defined **before** `$(DB_HOST)` in JDBC URL
- K8s 环境变量顺序：`DB_HOST` 必须定义在 JDBC URL 中 `$(DB_HOST)` **之前**
- Apollo liveness `initialDelaySeconds: 120` — Spring Boot startup > 60s
- Apollo 存活探针 `initialDelaySeconds: 120` — Spring Boot 启动 > 60s

### 4.5 InfluxDB Setup / InfluxDB 初始化

After Terraform creates the InfluxDB instance, you need to create an API token. The admin **password** ≠ API **token**.

Terraform 创建 InfluxDB 实例后，需要创建 API token。管理员**密码** ≠ API **Token**。

```bash
# From inside the cluster (InfluxDB is in VPC)
# 从集群内部执行（InfluxDB 在 VPC 内）
INFLUX_HOST="<endpoint-from-terraform-output>"

# Step 1: Sign in with admin password to get session cookie
# 步骤 1：用管理员密码登录获取 session cookie
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

> **How to get orgID / 如何获取 orgID:** Sign in first (first curl), then `GET /api/v2/orgs` to list organizations.
>
> 先登录（第一个 curl），再 `GET /api/v2/orgs` 列出组织。

Copy the `token` field from the response, then:
复制响应中的 `token` 字段，然后：

```bash
# Update secrets.auto.tfvars / 更新 secrets.auto.tfvars
# influxdb_api_token = "<paste-token-here>"

terraform apply -target=kubernetes_secret.agent
kubectl rollout restart deployment/agent-service -n zenalpha
```

### 4.6 Apollo Configuration Center / Apollo 配置中心

Apollo is deployed automatically by `deploy-k8s.sh`. The DB init job creates both `ApolloConfigDB` and `ApolloPortalDB` schemas.

Apollo 由 `deploy-k8s.sh` 自动部署。DB 初始化 Job 会创建 `ApolloConfigDB` 和 `ApolloPortalDB` 的 schema。

**Access Apollo Portal / 访问 Apollo Portal：**

```bash
kubectl port-forward svc/apollo-portal -n zenalpha 8070:8070
# Open http://localhost:8070  (admin / default password set in DB init)
# 打开 http://localhost:8070（admin / DB 初始化中设置的默认密码）
```

**Managed applications / 管理的应用：**

| App ID | Config Items / 配置项 |
|--------|----------------------|
| gateway | CORS origins, Eureka, Gateway routes, port |
| user-service | Eureka, JWT expiration, JPA/Hibernate |
| data-service | Eureka, JPA/Hibernate |
| signal-service | Eureka, JPA/Hibernate |
| notification-service | Eureka, JPA/Hibernate |
| backtest-service | Eureka, JPA/Hibernate |
| agent-service | InfluxDB connection, Polygon rate limit |

> **Note / 注意**: Sensitive values (DB password, JWT secret, InfluxDB token, Polygon API key) are **NOT** in Apollo. They're injected via K8s Secrets managed by Terraform.
>
> 敏感值（数据库密码、JWT 密钥、InfluxDB token、Polygon API key）**不在** Apollo 中，而是通过 Terraform 管理的 K8s Secrets 注入。

### 4.7 Frontend Deployment / 前端部署

The frontend is a React 18 SPA served from S3 + CloudFront.
前端是 React 18 SPA，通过 S3 + CloudFront 提供服务。

```bash
cd frontend
npm ci
npm run build

# Upload to S3 / 上传到 S3
aws s3 sync dist/ s3://zenalpha-prod-frontend --delete

# Invalidate CloudFront cache / 清除 CloudFront 缓存
DIST_ID=$(terraform -chdir=terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

**CloudFront routing / CloudFront 路由：**

| Path | Origin | Description |
|------|--------|-------------|
| `/api/*` | ALB (K8s gateway) | API requests proxied to backend / API 请求代理到后端 |
| `/*` | S3 bucket | Static frontend assets / 静态前端资源 |

---

## 5. Secret Management / 密钥管理

### Secret Flow / 密钥流转

```
secrets.auto.tfvars (gitignored)
        │
        ▼
    Terraform
        │
        ├──▶ kubernetes_secret "zenalpha-db-secret"   → DB host/user/password
        ├──▶ kubernetes_secret "zenalpha-secrets"      → JWT secret (auto-generated)
        ├──▶ kubernetes_secret "agent-secrets"         → InfluxDB URL + API token
        └──▶ kubernetes_secret "polygon-secret"        → Polygon API key
                │
                ▼
         K8s Pod env vars (via secretKeyRef)
```

### What goes where / 密钥存放位置

| Secret | Location / 位置 | Notes / 说明 |
|--------|-----------------|--------------|
| `db_password` | `secrets.auto.tfvars` | RDS master password / RDS 主密码 |
| `influxdb_password` | `secrets.auto.tfvars` | InfluxDB admin login password / InfluxDB 管理员登录密码 |
| `influxdb_api_token` | `secrets.auto.tfvars` | InfluxDB v2 API token (≠ password) / InfluxDB v2 API Token（≠密码） |
| `polygon_api_key` | `secrets.auto.tfvars` | Polygon.io market data API key / Polygon.io 行情 API 密钥 |
| JWT secret | Auto-generated | `random_password` in Terraform, 64 chars / Terraform 自动生成，64 字符 |

### Security checklist / 安全检查清单

- [x] `secrets.auto.tfvars` in `.gitignore`
- [x] No hardcoded secrets in source code / 源码无硬编码密钥
- [x] JWT secret has no default fallback / JWT 密钥无默认回退值
- [x] CORS restricted to CloudFront domain + localhost / CORS 限制为 CloudFront 域名 + localhost
- [x] RDS connections use SSL (`useSSL=true&requireSSL=true`) / RDS 连接使用 SSL
- [x] InfluxDB token is API token, not password / InfluxDB token 是 API Token 而非密码

---

## 6. Day-2 Operations / 日常运维

### Update a single service / 更新单个服务

```bash
# Rebuild / 重新构建
cd services && mvn clean package -pl signal-service -am -DskipTests
docker build -t $ECR_REGISTRY/zenalpha-signal-service:latest -f services/signal-service/Dockerfile services/
docker push $ECR_REGISTRY/zenalpha-signal-service:latest

# Deploy / 部署
scripts/deploy-k8s.sh signal-service
# Or simply / 或者直接
kubectl rollout restart deployment/signal-service -n zenalpha
```

### Scale services / 服务扩缩容

```bash
kubectl scale deployment/gateway -n zenalpha --replicas=3
# Karpenter will auto-provision nodes if needed / Karpenter 会自动扩容节点
```

### View logs / 查看日志

```bash
kubectl logs -f deployment/gateway -n zenalpha --tail=100
kubectl logs -f deployment/agent-service -n zenalpha --tail=100 | grep -v "GET /health"
```

### Check Eureka registry / 检查 Eureka 注册表

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

### Update Apollo config / 更新 Apollo 配置

```bash
kubectl port-forward svc/apollo-portal -n zenalpha 8070:8070
# Open http://localhost:8070, edit configs in web UI, then publish
# 打开 http://localhost:8070，在 Web UI 中编辑配置，然后发布
```

### Rotate secrets / 轮换密钥

```bash
# 1. Update secrets.auto.tfvars with new values / 更新密钥文件
# 2. Apply / 执行
terraform apply -target=kubernetes_secret.db -target=kubernetes_secret.agent
# 3. Restart affected services / 重启相关服务
kubectl rollout restart deployment -n zenalpha
```

### Sync market data / 同步行情数据

```bash
# One-time sync / 一次性同步
python3 scripts/sync_polygon.py --symbols AAPL,TSLA,NVDA --days 365

# CronJob is deployed automatically for daily sync
# 每日同步的 CronJob 已自动部署
kubectl get cronjob -n zenalpha
```

---

## 7. Troubleshooting / 故障排查

### Pod stuck in Pending / Pod 一直 Pending

```bash
kubectl describe pod <pod-name> -n zenalpha | tail -10
```

**Common causes / 常见原因:**

| Symptom | Cause / 原因 | Fix / 修复 |
|---------|-------------|-----------|
| `Insufficient cpu/memory` | Nodes full / 节点资源满 | Check Karpenter NodePool limits, increase `cpu`/`memory` limits / 检查 NodePool 限制 |
| `SubnetsNotFound` | Missing `karpenter.sh/discovery` tags / 缺少标签 | `terraform apply` to restore tags / 执行 terraform apply 恢复标签 |
| `node affinity` | Trying to schedule on wrong node type / 调度到错误节点类型 | Check pod nodeSelector/affinity / 检查 pod 的 nodeSelector |

### Eureka registry empty / Eureka 注册表为空

After node migrations, services may lose registration.
节点迁移后，服务可能丢失注册。

```bash
kubectl rollout restart deployment -n zenalpha    # Restart all / 全部重启
```

### Agent-service InfluxDB errors / Agent-service InfluxDB 错误

| Error | Cause / 原因 | Fix / 修复 |
|-------|-------------|-----------|
| `ConnectTimeoutError port=80` | Missing `https://` + `:8086` in URL | Fix `influxdb-url` in `k8s.tf`, `terraform apply` |
| `401 Unauthorized` | Using password instead of API token / 用了密码而非 API token | Create API token (section 4.5), update secret / 创建 API token（4.5节） |
| `404 bucket not found` | Bucket not created / Bucket 未创建 | Create via InfluxDB UI or API / 通过 UI 或 API 创建 |

### Apollo CrashLoopBackOff / Apollo 崩溃循环

| Error | Cause / 原因 | Fix / 修复 |
|-------|-------------|-----------|
| `Table 'ApolloConfigDB.ServerConfig' doesn't exist` | DB not initialized / 数据库未初始化 | Run `deploy-k8s.sh apollo` (runs init job) / 执行 deploy-k8s.sh apollo |
| `UnknownHostException: $(DB_HOST)` | Env var ordering wrong / 环境变量顺序错误 | `DB_HOST` must be defined before `$(DB_HOST)` in YAML / DB_HOST 必须在 $(DB_HOST) 之前 |
| Killed by liveness probe / 被存活探针杀死 | `initialDelaySeconds` too low / 太低 | Set to 120+ for Spring Boot / Spring Boot 设为 120+ |

### K8s env var `$(VAR)` not resolved / K8s 环境变量未解析

If you see literal `$(DB_HOST)` in logs, two possible causes:
如果日志中看到字面量 `$(DB_HOST)`，两种可能原因：

1. **envsubst corruption** — `envsubst` without scope replaces everything. Fix: `envsubst '${ECR_REGISTRY}'`
2. **Declaration order** — Referenced var must be declared above the reference in the env list.

1. **envsubst 破坏** — 不限制范围的 envsubst 会替换所有变量。修复：`envsubst '${ECR_REGISTRY}'`
2. **声明顺序** — 被引用的变量必须在 env 列表中声明在引用之前

---

## 8. Cost Optimization / 成本优化

### Current production cost estimate / 当前生产成本估算

| Resource | Spec | Monthly Cost (est.) |
|----------|------|-------------------|
| EKS cluster | Control plane | $73 |
| Managed Node Group | 1x t3.medium (Karpenter only) | ~$30 |
| Karpenter Nodes | 2-3x c7i.large (auto-scaled) | ~$120-180 |
| RDS MySQL | db.t3.micro, single-AZ, 20GB | ~$15 |
| Timestream InfluxDB | db.influx.medium | ~$64 |
| NAT Gateway | Single, shared | ~$32 + data transfer |
| CloudFront | Standard, with WAF | ~$5-20 (traffic dependent) |
| ECR | ~2GB images | ~$1 |
| **Total** | | **~$340-415/mo** |

### Cost-saving tips / 省钱技巧

- **Single NAT Gateway** — already implemented. Multi-AZ NAT costs 3x.
  已实施单 NAT Gateway。多 AZ NAT 费用为 3 倍。
- **Karpenter `WhenEmpty` consolidation** — removes idle nodes after 30 min.
  Karpenter `WhenEmpty` 合并策略 — 30 分钟后移除空闲节点。
- **RDS single-AZ** — fine for dev/staging, enable Multi-AZ for production.
  RDS 单 AZ — 开发/测试可以，生产环境开启 Multi-AZ。
- **Spot instances** — add `spot` to NodePool `capacity-type` for non-critical workloads.
  Spot 实例 — 在 NodePool 的 `capacity-type` 中添加 `spot` 用于非关键负载。

---

## File Reference / 文件参考

```
zenalpha/
├── terraform/
│   ├── main.tf                    # Module composition / 模块组合
│   ├── variables.tf               # Input variables / 输入变量
│   ├── outputs.tf                 # Output values / 输出值
│   ├── versions.tf                # Provider versions / Provider 版本
│   ├── k8s.tf                     # K8s namespace, secrets, configmaps
│   ├── terraform.tfvars           # Non-secret config (committed) / 非敏感配置（提交）
│   ├── secrets.auto.tfvars        # Secrets (gitignored) / 密钥（不提交）
│   ├── modules/
│   │   ├── vpc/                   # VPC, subnets, NAT
│   │   ├── eks/                   # EKS cluster, node group, OIDC
│   │   ├── rds/                   # MySQL instance
│   │   ├── ecr/                   # Container registries
│   │   ├── timestream/            # InfluxDB instance
│   │   └── frontend/              # S3 + CloudFront + WAF
│   └── k8s/                       # K8s YAML manifests
│       ├── namespace.yaml
│       ├── eureka/                # StatefulSet + Service
│       ├── apollo/                # DB init job + 3 Deployments + Services
│       ├── gateway/               # Deployment + LoadBalancer Service
│       ├── user-service/          # Deployment + Service
│       ├── data-service/
│       ├── signal-service/
│       ├── backtest-service/
│       ├── notification-service/
│       └── agent-service/         # Deployment + CronJob
├── scripts/
│   ├── build-all.sh               # Build all images + push to ECR
│   ├── deploy-k8s.sh              # Deploy all K8s resources
│   └── sync_polygon.py            # Market data sync script
├── services/                      # Java microservices (Spring Boot)
├── chanquant/                     # Python Chan Theory engine
└── frontend/                      # React 18 + TypeScript + Tailwind
```
