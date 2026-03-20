# =============================================================================
# Kubernetes Provider + Foundational Resources
# Manages: namespace, secrets, configmaps that other K8s resources depend on.
# =============================================================================

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------
resource "kubernetes_namespace" "zenalpha" {
  metadata {
    name = var.project_name
    labels = {
      project     = var.project_name
      environment = var.environment
      managed-by  = "terraform"
    }
  }
}

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

# RDS credentials — used by all Java services and Apollo
resource "kubernetes_secret" "db" {
  metadata {
    name      = "zenalpha-db-secret"
    namespace = kubernetes_namespace.zenalpha.metadata[0].name
  }
  data = {
    host     = module.rds.address
    username = var.db_username
    password = var.db_password
  }
}

# JWT signing key — used by gateway + user-service
resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "kubernetes_secret" "jwt" {
  metadata {
    name      = "zenalpha-secrets"
    namespace = kubernetes_namespace.zenalpha.metadata[0].name
  }
  data = {
    jwt-secret = random_password.jwt_secret.result
  }
}

# Agent service secrets (InfluxDB + Polygon)
resource "kubernetes_secret" "agent" {
  metadata {
    name      = "agent-secrets"
    namespace = kubernetes_namespace.zenalpha.metadata[0].name
  }
  data = {
    influxdb-url   = "https://${module.timestream.endpoint}:8086"
    influxdb-token = var.influxdb_api_token
  }
}

resource "kubernetes_secret" "polygon" {
  metadata {
    name      = "polygon-secret"
    namespace = kubernetes_namespace.zenalpha.metadata[0].name
  }
  data = {
    api-key = var.polygon_api_key
  }
}

# ---------------------------------------------------------------------------
# ConfigMap — deploy metadata used by scripts/deploy-k8s.sh
# ---------------------------------------------------------------------------
resource "kubernetes_config_map" "deploy_metadata" {
  metadata {
    name      = "deploy-metadata"
    namespace = kubernetes_namespace.zenalpha.metadata[0].name
  }
  data = {
    ecr-registry        = split("/", module.ecr.repository_urls["gateway"])[0]
    cloudfront-domain   = module.frontend.cloudfront_domain_name
    rds-address         = module.rds.address
    influxdb-url        = "https://${module.timestream.endpoint}:8086"
    eks-cluster-name    = module.eks.cluster_name
    region              = var.region
  }
}

# ---------------------------------------------------------------------------
# Gateway ConfigMap — routes + CORS origins
# ---------------------------------------------------------------------------
resource "kubernetes_config_map" "gateway" {
  metadata {
    name      = "gateway-config"
    namespace = kubernetes_namespace.zenalpha.metadata[0].name
    labels    = { app = "gateway" }
  }
  data = {
    cors-allowed-origins = "https://${module.frontend.cloudfront_domain_name},http://localhost:5173"
    "application.yml" = yamlencode({
      server = { port = 8080 }
      spring = {
        cloud = {
          gateway = {
            httpclient = {
              connect-timeout = 5000
              response-timeout = "PT180S"
            }
            routes = [
              { id = "signal-service",       uri = "lb://signal-service",       predicates = ["Path=/api/signals/**"] },
              { id = "backtest-service",     uri = "lb://backtest-service",     predicates = ["Path=/api/backtest/**"] },
              { id = "data-service",         uri = "lb://data-service",         predicates = ["Path=/api/data/**"] },
              { id = "user-service",         uri = "lb://user-service",         predicates = ["Path=/api/users/**,/api/auth/**"] },
              { id = "notification-service", uri = "lb://notification-service", predicates = ["Path=/api/notifications/**"] },
              {
                id         = "agent-service"
                uri        = "http://agent-service.zenalpha.svc.cluster.local:8090"
                predicates = ["Path=/api/agents/**"]
                filters    = ["StripPrefix=2"]
                metadata   = { response-timeout = 180000, connect-timeout = 5000 }
              },
            ]
            default-filters = ["DedupeResponseHeader=Access-Control-Allow-Credentials Access-Control-Allow-Origin"]
          }
        }
      }
      eureka = {
        client = { serviceUrl = { defaultZone = "http://eureka-server.zenalpha.svc.cluster.local:8761/eureka/" } }
      }
    })
  }
}
