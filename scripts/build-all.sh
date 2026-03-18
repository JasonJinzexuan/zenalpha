#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ECR_REGISTRY="${ECR_REGISTRY:-}"
TAG="${TAG:-latest}"

echo "=== ZenAlpha Build All ==="

# Build Java services
echo "[1/3] Building Java services with Maven..."
cd "$PROJECT_ROOT/services"
mvn clean package -DskipTests -q
echo "  Maven build complete."

# Build Docker images
echo "[2/3] Building Docker images..."

SERVICES=(
    "eureka-server:8761"
    "gateway:8080"
    "signal-service:8081"
    "backtest-service:8082"
    "data-service:8083"
    "user-service:8084"
    "notification-service:8085"
)

for entry in "${SERVICES[@]}"; do
    service="${entry%%:*}"
    port="${entry##*:}"
    echo "  Building $service..."
    docker build \
        -t "zenalpha-${service}:${TAG}" \
        -f "$PROJECT_ROOT/services/${service}/Dockerfile" \
        "$PROJECT_ROOT/services"
done

# Build frontend
echo "[3/3] Building frontend..."
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    npm ci
fi
npm run build
docker build -t "zenalpha-frontend:${TAG}" "$PROJECT_ROOT/frontend"

echo ""
echo "=== Build Complete ==="
echo ""

# Tag and push to ECR if registry is set
if [ -n "$ECR_REGISTRY" ]; then
    echo "Pushing to ECR: $ECR_REGISTRY"
    aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin "$ECR_REGISTRY"

    for entry in "${SERVICES[@]}"; do
        service="${entry%%:*}"
        docker tag "zenalpha-${service}:${TAG}" "${ECR_REGISTRY}/zenalpha-${service}:${TAG}"
        docker push "${ECR_REGISTRY}/zenalpha-${service}:${TAG}"
        echo "  Pushed $service"
    done

    docker tag "zenalpha-frontend:${TAG}" "${ECR_REGISTRY}/zenalpha-frontend:${TAG}"
    docker push "${ECR_REGISTRY}/zenalpha-frontend:${TAG}"
    echo "  Pushed frontend"

    echo ""
    echo "=== ECR Push Complete ==="
fi
