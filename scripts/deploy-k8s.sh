#!/usr/bin/env bash
###############################################################################
# deploy-k8s.sh — Deploy all K8s resources for zenalpha
#
# Prerequisites:
#   1. terraform apply completed (creates EKS, RDS, ECR, secrets, configmaps)
#   2. Docker images pushed to ECR
#   3. kubectl configured for the target cluster
#
# Usage:
#   ./scripts/deploy-k8s.sh              # full deploy
#   ./scripts/deploy-k8s.sh apollo       # deploy only apollo
#   ./scripts/deploy-k8s.sh gateway      # deploy only gateway
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
K8S_DIR="$SCRIPT_DIR/../terraform/k8s"
NAMESPACE="zenalpha"

# ---------------------------------------------------------------------------
# Resolve ECR_REGISTRY from Terraform output or K8s configmap
# ---------------------------------------------------------------------------
resolve_ecr_registry() {
  if [[ -n "${ECR_REGISTRY:-}" ]]; then
    return
  fi

  # Try K8s configmap first (works if terraform already applied)
  ECR_REGISTRY=$(kubectl get configmap deploy-metadata -n "$NAMESPACE" \
    -o jsonpath='{.data.ecr-registry}' 2>/dev/null || true)

  if [[ -z "$ECR_REGISTRY" ]]; then
    # Fallback: parse from terraform output
    ECR_REGISTRY=$(cd "$SCRIPT_DIR/../terraform" && \
      terraform output -raw ecr_repository_urls 2>/dev/null | \
      head -1 | cut -d/ -f1 || true)
  fi

  if [[ -z "$ECR_REGISTRY" ]]; then
    echo "ERROR: Cannot resolve ECR_REGISTRY. Set it manually:"
    echo "  export ECR_REGISTRY=<account-id>.dkr.ecr.<region>.amazonaws.com"
    exit 1
  fi

  export ECR_REGISTRY
  echo "ECR_REGISTRY=$ECR_REGISTRY"
}

# ---------------------------------------------------------------------------
# Apply a K8s YAML file, substituting only ${ECR_REGISTRY}
# ---------------------------------------------------------------------------
apply_template() {
  local file="$1"
  echo "  Applying $file"
  envsubst '${ECR_REGISTRY}' < "$file" | kubectl apply -f -
}

apply_raw() {
  local file="$1"
  echo "  Applying $file"
  kubectl apply -f "$file"
}

# ---------------------------------------------------------------------------
# Wait for a deployment to be ready
# ---------------------------------------------------------------------------
wait_ready() {
  local name="$1"
  local timeout="${2:-180s}"
  echo "  Waiting for $name (timeout $timeout)..."
  kubectl rollout status "deployment/$name" -n "$NAMESPACE" --timeout="$timeout" || true
}

# ---------------------------------------------------------------------------
# Deploy components
# ---------------------------------------------------------------------------

deploy_namespace() {
  echo "=== Namespace ==="
  apply_raw "$K8S_DIR/namespace.yaml"
}

deploy_eureka() {
  echo "=== Eureka ==="
  apply_raw "$K8S_DIR/eureka/configmap.yaml"
  apply_template "$K8S_DIR/eureka/statefulset.yaml"
  apply_raw "$K8S_DIR/eureka/service.yaml"
  echo "  Waiting for eureka-server-0..."
  kubectl rollout status statefulset/eureka-server -n "$NAMESPACE" --timeout=180s || true
}

deploy_apollo() {
  echo "=== Apollo ==="
  # Step 1: Init DB (idempotent)
  kubectl delete job apollo-db-init-full -n "$NAMESPACE" --ignore-not-found 2>/dev/null
  apply_raw "$K8S_DIR/apollo/db-init-full.yaml"
  echo "  Waiting for Apollo DB init job..."
  kubectl wait --for=condition=complete job/apollo-db-init-full \
    -n "$NAMESPACE" --timeout=120s 2>/dev/null || {
    echo "  WARN: DB init job not yet complete, continuing..."
  }

  # Step 2: Deploy services
  apply_raw "$K8S_DIR/apollo/deployment.yaml"
  apply_raw "$K8S_DIR/apollo/service.yaml"
  wait_ready apollo-configservice 180s
  wait_ready apollo-adminservice 180s
  wait_ready apollo-portal 180s
}

deploy_gateway() {
  echo "=== Gateway ==="
  # ConfigMap is managed by Terraform (k8s.tf), just apply deployment + service
  apply_template "$K8S_DIR/gateway/deployment.yaml"
  apply_raw "$K8S_DIR/gateway/service.yaml"
  wait_ready gateway
}

deploy_service() {
  local name="$1"
  echo "=== $name ==="
  apply_template "$K8S_DIR/$name/deployment.yaml"
  apply_raw "$K8S_DIR/$name/service.yaml"

  # Apply HPA if exists
  local hpa="$K8S_DIR/$name/hpa.yaml"
  [[ -f "$hpa" ]] && apply_raw "$hpa"

  wait_ready "$name"
}

deploy_agent_service() {
  echo "=== Agent Service ==="
  apply_raw "$K8S_DIR/agent-service/deployment.yaml"
  # CronJob
  [[ -f "$K8S_DIR/agent-service/cronjob.yaml" ]] && \
    apply_raw "$K8S_DIR/agent-service/cronjob.yaml"
  wait_ready agent-service
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  local target="${1:-all}"

  resolve_ecr_registry

  case "$target" in
    all)
      deploy_namespace
      deploy_eureka
      deploy_apollo
      deploy_gateway
      deploy_service user-service
      deploy_service data-service
      deploy_service signal-service
      deploy_service backtest-service
      deploy_service notification-service
      deploy_agent_service
      ;;
    namespace)      deploy_namespace ;;
    eureka)         deploy_eureka ;;
    apollo)         deploy_apollo ;;
    gateway)        deploy_gateway ;;
    agent-service)  deploy_agent_service ;;
    *)              deploy_service "$target" ;;
  esac

  echo ""
  echo "=== Deploy complete ==="
  kubectl get pods -n "$NAMESPACE"
}

main "$@"
