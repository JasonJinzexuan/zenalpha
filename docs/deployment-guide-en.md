# ZenAlpha Deployment Guide

> **Last updated**: 2026-03-18

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Architecture Overview](#2-architecture-overview)
3. [Quick Start (Fresh Deploy)](#3-quick-start-fresh-deploy)
4. [Step-by-Step Guide](#4-step-by-step-guide)
   - [4.1 Terraform — Infrastructure](#41-terraform--infrastructure)
   - [4.2 Karpenter — Auto Scaling](#42-karpenter--auto-scaling)
   - [4.3 Build & Push Docker Images](#43-build--push-docker-images)
   - [4.4 Deploy K8s Workloads](#44-deploy-k8s-workloads)
   - [4.5 InfluxDB Setup](#45-influxdb-setup)
   - [4.6 Apollo Configuration Center](#46-apollo-configuration-center)
   - [4.7 Frontend Deployment](#47-frontend-deployment)
5. [Secret Management](#5-secret-management)
6. [Day-2 Operations](#6-day-2-operations)
7. [Troubleshooting](#7-troubleshooting)
8. [Cost Optimization](#8-cost-optimization)

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| AWS CLI | >= 2.x | AWS resource management |
| Terraform | >= 1.5.0 | Infrastructure as Code |
| kubectl | >= 1.28 | K8s cluster management |
| Docker | >= 24.x | Container image build |
| Maven | >= 3.9 | Java service build |
| Node.js | >= 18 | Frontend build |
| Helm | >= 3.x | Karpenter installation |

**AWS permissions required:**

The deploying IAM user/role needs permissions for: EKS, EC2, VPC, RDS, ECR, S3, CloudFront, WAF, Timestream InfluxDB, IAM.
Recommended: use `AdministratorAccess` for initial setup, then scope down.

---

## 2. Architecture Overview

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

External:  Polygon.io (market data source)
```

**Terraform modules:**

| Module | Resources Created |
|--------|------------------|
| `vpc` | VPC, 3 public + 3 private subnets, IGW, NAT GW, route tables |
| `eks` | EKS cluster, managed node group, OIDC provider, IAM roles, security groups |
| `rds` | RDS MySQL instance, subnet group, security group |
| `ecr` | ECR repositories for all services |
| `timestream` | Timestream InfluxDB instance, security group, IAM role for IRSA |
| `frontend` | S3 bucket, CloudFront distribution, WAF (us-east-1), OAC |
| `k8s.tf` | K8s namespace, secrets (DB, JWT, agent, polygon), configmaps |

---

## 3. Quick Start (Fresh Deploy)

For experienced users — the complete sequence in one block.

```bash
# ---- Step 1: Terraform ----
cd terraform
cp terraform.tfvars.example terraform.tfvars   # Edit values
cat > secrets.auto.tfvars << 'EOF'
db_password        = "<generate-strong-password>"
influxdb_password  = "<generate-strong-password>"
influxdb_api_token = "<created-after-step-5>"      # Placeholder first
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

## 4. Step-by-Step Guide

### 4.1 Terraform — Infrastructure

#### 4.1.1 Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
project_name = "zenalpha"
environment  = "prod"
region       = "us-west-2"

# EKS — Managed Node Group (runs Karpenter only)
eks_node_instance_type = "t3.medium"
eks_node_count         = 1
eks_node_min           = 1
eks_node_max           = 1

# RDS
db_instance_class = "db.t3.micro"    # Upgrade to db.r6g.large for production
db_name           = "zenalpha"
db_username       = "zenalpha_admin"
db_multi_az       = false             # Set true for production HA
db_storage_gb     = 20

# Domain (optional)
domain_name         = ""
acm_certificate_arn = ""
api_gateway_domain  = ""              # Fill after first deploy
```

#### 4.1.2 Configure Secrets

Create `secrets.auto.tfvars` (gitignored):

```bash
cat > secrets.auto.tfvars << 'EOF'
# DO NOT COMMIT — gitignored
db_password        = "$(openssl rand -base64 24)"
influxdb_password  = "$(openssl rand -base64 24)"
influxdb_api_token = "placeholder"    # Will be updated after InfluxDB init
polygon_api_key    = "your-polygon-key-here"
EOF
```

> **Important**: Generate real passwords. `influxdb_api_token` is a placeholder — you'll create a real one in [step 4.5](#45-influxdb-setup).

#### 4.1.3 Apply

```bash
terraform init
terraform apply
```

Expected time: ~20 minutes (RDS and InfluxDB take the longest).

#### 4.1.4 Configure kubectl

```bash
# Command is also in terraform output
aws eks update-kubeconfig --name zenalpha-prod-eks --region us-west-2
kubectl get nodes   # Should see 1 t3.medium node
```

### 4.2 Karpenter — Auto Scaling

Karpenter manages worker nodes (c7i.large) for all application pods. The managed node group (1x t3.medium) only runs the Karpenter controller itself.

#### 4.2.1 Install Karpenter

```bash
CLUSTER_NAME="zenalpha-prod-eks"
CLUSTER_ENDPOINT=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.endpoint" --output text)
KARPENTER_VERSION="1.1.1"  # Check latest: https://github.com/aws/karpenter-provider-aws/releases

helm install karpenter oci://public.ecr.aws/karpenter/karpenter \
  --namespace kube-system \
  --set "settings.clusterName=$CLUSTER_NAME" \
  --set "settings.clusterEndpoint=$CLUSTER_ENDPOINT" \
  --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::<ACCOUNT_ID>:role/zenalpha-prod-karpenter-role" \
  --version "$KARPENTER_VERSION" \
  --wait
```

#### 4.2.2 Create NodePool + EC2NodeClass

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

> **Why c7i.large?** Compute-optimized, ~30% better price-performance than t3.medium for sustained workloads. No burstable credit surprises.

> **Why keep 1x t3.medium?** Karpenter controller has `nodeAffinity: karpenter.sh/nodepool DoesNotExist` — it cannot run on nodes it manages (to prevent self-eviction). The managed node group provides this safe harbor.

### 4.3 Build & Push Docker Images

```bash
export ECR_REGISTRY=$(terraform -chdir=terraform output -raw ecr_registry)
scripts/build-all.sh
```

This script:
- Builds all 7 Java services with Maven (single multi-module build)
- Builds the agent-service (Python) Docker image
- Builds the frontend Docker image (not used in S3 deploy, but available)
- Tags and pushes all images to ECR

**To build a single service:**

```bash
cd services && mvn clean package -pl gateway -am -DskipTests
docker build -t $ECR_REGISTRY/zenalpha-gateway:latest -f services/gateway/Dockerfile services/
docker push $ECR_REGISTRY/zenalpha-gateway:latest
```

### 4.4 Deploy K8s Workloads

```bash
scripts/deploy-k8s.sh          # Full deploy
```

**Deployment order (handled automatically):**

```
1. namespace
2. eureka (service registry — must be up before other services)
3. apollo (DB init job → configservice → adminservice → portal)
4. gateway (Spring Cloud Gateway)
5. user-service, data-service, signal-service, backtest-service, notification-service
6. agent-service (Python FastAPI)
```

**Selective deploy:**

```bash
scripts/deploy-k8s.sh gateway        # Only gateway
scripts/deploy-k8s.sh apollo         # Only apollo
scripts/deploy-k8s.sh user-service   # Only user-service
```

**Key implementation details:**

- `envsubst '${ECR_REGISTRY}'` — only substitutes ECR registry, leaves K8s `$(VAR)` references intact
- K8s env var ordering: `DB_HOST` must be defined **before** `$(DB_HOST)` in JDBC URL
- Apollo liveness `initialDelaySeconds: 120` — Spring Boot startup > 60s

### 4.5 InfluxDB Setup

After Terraform creates the InfluxDB instance, you need to create an API token. The admin **password** ≠ API **token**.

```bash
# From inside the cluster (InfluxDB is in VPC)
INFLUX_HOST="<endpoint-from-terraform-output>"

# Step 1: Sign in with admin password to get session cookie
# Step 2: Create API token
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

> **How to get orgID:** Sign in first (first curl), then `GET /api/v2/orgs` to list organizations.

Copy the `token` field from the response, then:

```bash
# Update secrets.auto.tfvars
# influxdb_api_token = "<paste-token-here>"

terraform apply -target=kubernetes_secret.agent
kubectl rollout restart deployment/agent-service -n zenalpha
```

### 4.6 Apollo Configuration Center

Apollo is deployed automatically by `deploy-k8s.sh`. The DB init job creates both `ApolloConfigDB` and `ApolloPortalDB` schemas.

**Access Apollo Portal:**

```bash
kubectl port-forward svc/apollo-portal -n zenalpha 8070:8070
# Open http://localhost:8070  (admin / default password set in DB init)
```

**Managed applications:**

| App ID | Config Items |
|--------|-------------|
| gateway | CORS origins, Eureka, Gateway routes, port |
| user-service | Eureka, JWT expiration, JPA/Hibernate |
| data-service | Eureka, JPA/Hibernate |
| signal-service | Eureka, JPA/Hibernate |
| notification-service | Eureka, JPA/Hibernate |
| backtest-service | Eureka, JPA/Hibernate |
| agent-service | InfluxDB connection, Polygon rate limit |

> **Note**: Sensitive values (DB password, JWT secret, InfluxDB token, Polygon API key) are **NOT** in Apollo. They're injected via K8s Secrets managed by Terraform.

### 4.7 Frontend Deployment

The frontend is a React 18 SPA served from S3 + CloudFront.

```bash
cd frontend
npm ci
npm run build

# Upload to S3
aws s3 sync dist/ s3://zenalpha-prod-frontend --delete

# Invalidate CloudFront cache
DIST_ID=$(terraform -chdir=terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

**CloudFront routing:**

| Path | Origin | Description |
|------|--------|-------------|
| `/api/*` | ALB (K8s gateway) | API requests proxied to backend |
| `/*` | S3 bucket | Static frontend assets |

---

## 5. Secret Management

### Secret Flow

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

### What goes where

| Secret | Location | Notes |
|--------|----------|-------|
| `db_password` | `secrets.auto.tfvars` | RDS master password |
| `influxdb_password` | `secrets.auto.tfvars` | InfluxDB admin login password |
| `influxdb_api_token` | `secrets.auto.tfvars` | InfluxDB v2 API token (≠ password) |
| `polygon_api_key` | `secrets.auto.tfvars` | Polygon.io market data API key |
| JWT secret | Auto-generated | `random_password` in Terraform, 64 chars |

### Security checklist

- [x] `secrets.auto.tfvars` in `.gitignore`
- [x] No hardcoded secrets in source code
- [x] JWT secret has no default fallback
- [x] CORS restricted to CloudFront domain + localhost
- [x] RDS connections use SSL (`useSSL=true&requireSSL=true`)
- [x] InfluxDB token is API token, not password

---

## 6. Day-2 Operations

### Update a single service

```bash
# Rebuild
cd services && mvn clean package -pl signal-service -am -DskipTests
docker build -t $ECR_REGISTRY/zenalpha-signal-service:latest -f services/signal-service/Dockerfile services/
docker push $ECR_REGISTRY/zenalpha-signal-service:latest

# Deploy
scripts/deploy-k8s.sh signal-service
# Or simply
kubectl rollout restart deployment/signal-service -n zenalpha
```

### Scale services

```bash
kubectl scale deployment/gateway -n zenalpha --replicas=3
# Karpenter will auto-provision nodes if needed
```

### View logs

```bash
kubectl logs -f deployment/gateway -n zenalpha --tail=100
kubectl logs -f deployment/agent-service -n zenalpha --tail=100 | grep -v "GET /health"
```

### Check Eureka registry

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

### Update Apollo config

```bash
kubectl port-forward svc/apollo-portal -n zenalpha 8070:8070
# Open http://localhost:8070, edit configs in web UI, then publish
```

### Rotate secrets

```bash
# 1. Update secrets.auto.tfvars with new values
# 2. Apply
terraform apply -target=kubernetes_secret.db -target=kubernetes_secret.agent
# 3. Restart affected services
kubectl rollout restart deployment -n zenalpha
```

### Sync market data

```bash
# One-time sync
python3 scripts/sync_polygon.py --symbols AAPL,TSLA,NVDA --days 365

# CronJob is deployed automatically for daily sync
kubectl get cronjob -n zenalpha
```

---

## 7. Troubleshooting

### Pod stuck in Pending

```bash
kubectl describe pod <pod-name> -n zenalpha | tail -10
```

**Common causes:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Insufficient cpu/memory` | Nodes full | Check Karpenter NodePool limits, increase `cpu`/`memory` limits |
| `SubnetsNotFound` | Missing `karpenter.sh/discovery` tags | `terraform apply` to restore tags |
| `node affinity` | Trying to schedule on wrong node type | Check pod nodeSelector/affinity |

### Eureka registry empty

After node migrations, services may lose registration.

```bash
kubectl rollout restart deployment -n zenalpha    # Restart all
```

### Agent-service InfluxDB errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectTimeoutError port=80` | Missing `https://` + `:8086` in URL | Fix `influxdb-url` in `k8s.tf`, `terraform apply` |
| `401 Unauthorized` | Using password instead of API token | Create API token (section 4.5), update secret |
| `404 bucket not found` | Bucket not created | Create via InfluxDB UI or API |

### Apollo CrashLoopBackOff

| Error | Cause | Fix |
|-------|-------|-----|
| `Table 'ApolloConfigDB.ServerConfig' doesn't exist` | DB not initialized | Run `deploy-k8s.sh apollo` (runs init job) |
| `UnknownHostException: $(DB_HOST)` | Env var ordering wrong | `DB_HOST` must be defined before `$(DB_HOST)` in YAML |
| Killed by liveness probe | `initialDelaySeconds` too low | Set to 120+ for Spring Boot |

### K8s env var `$(VAR)` not resolved

If you see literal `$(DB_HOST)` in logs, two possible causes:

1. **envsubst corruption** — `envsubst` without scope replaces everything. Fix: `envsubst '${ECR_REGISTRY}'`
2. **Declaration order** — Referenced var must be declared above the reference in the env list.

---

## 8. Cost Optimization

### Current production cost estimate

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

### Cost-saving tips

- **Single NAT Gateway** — already implemented. Multi-AZ NAT costs 3x.
- **Karpenter `WhenEmpty` consolidation** — removes idle nodes after 30 min.
- **RDS single-AZ** — fine for dev/staging, enable Multi-AZ for production.
- **Spot instances** — add `spot` to NodePool `capacity-type` for non-critical workloads.

---

## File Reference

```
zenalpha/
├── terraform/
│   ├── main.tf                    # Module composition
│   ├── variables.tf               # Input variables
│   ├── outputs.tf                 # Output values
│   ├── versions.tf                # Provider versions
│   ├── k8s.tf                     # K8s namespace, secrets, configmaps
│   ├── terraform.tfvars           # Non-secret config (committed)
│   ├── secrets.auto.tfvars        # Secrets (gitignored)
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
