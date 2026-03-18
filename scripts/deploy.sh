#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TF_DIR="$PROJECT_ROOT/terraform"
K8S_DIR="$TF_DIR/k8s"

echo "=== ZenAlpha Deploy ==="
echo ""

# Step 1: Terraform
echo "[1/4] Applying Terraform infrastructure..."
cd "$TF_DIR"

if [ ! -f "terraform.tfvars" ]; then
    echo "ERROR: terraform.tfvars not found. Copy terraform.tfvars.example and fill in values."
    exit 1
fi

terraform init
terraform plan -out=tfplan
echo ""
read -p "Apply Terraform plan? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    terraform apply tfplan
fi

# Extract outputs
EKS_CLUSTER=$(terraform output -raw eks_cluster_name)
ECR_REGISTRY=$(terraform output -raw ecr_registry_url)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
CF_DOMAIN=$(terraform output -raw cloudfront_domain_name)

echo "  EKS Cluster: $EKS_CLUSTER"
echo "  ECR Registry: $ECR_REGISTRY"
echo "  RDS Endpoint: $RDS_ENDPOINT"
echo "  CloudFront: $CF_DOMAIN"

# Step 2: Configure kubectl
echo ""
echo "[2/4] Configuring kubectl..."
aws eks update-kubeconfig --name "$EKS_CLUSTER" --region us-west-2

# Step 3: Initialize database
echo ""
echo "[3/4] Initializing database..."
echo "  Run this manually:"
echo "  mysql -h $RDS_ENDPOINT -u admin -p < $SCRIPT_DIR/init-db.sql"

# Step 4: Deploy to K8s
echo ""
echo "[4/4] Deploying to Kubernetes..."

# Build and push images first
export ECR_REGISTRY
export TAG="latest"
bash "$SCRIPT_DIR/build-all.sh"

# Apply K8s manifests
echo "Applying K8s manifests..."
kubectl apply -f "$K8S_DIR/namespace.yaml"

# Replace ECR registry placeholder in manifests
for dir in eureka apollo gateway signal-service backtest-service data-service user-service notification-service; do
    if [ -d "$K8S_DIR/$dir" ]; then
        for file in "$K8S_DIR/$dir"/*.yaml; do
            sed "s|\${ECR_REGISTRY}|$ECR_REGISTRY|g" "$file" | kubectl apply -f -
        done
    fi
done

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Frontend URL: https://$CF_DOMAIN"
echo "API Gateway:  kubectl get svc -n zenalpha gateway"
echo ""
echo "Check status: kubectl get pods -n zenalpha"
