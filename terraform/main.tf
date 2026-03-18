locals {
  cluster_name = "${var.project_name}-${var.environment}-eks"
}

# VPC
module "vpc" {
  source = "./modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  cluster_name = local.cluster_name
}

# EKS
module "eks" {
  source = "./modules/eks"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
  cluster_name       = local.cluster_name
  node_instance_type = var.eks_node_instance_type
  node_count         = var.eks_node_count
  node_min           = var.eks_node_min
  node_max           = var.eks_node_max
}

# RDS
module "rds" {
  source = "./modules/rds"

  project_name               = var.project_name
  environment                = var.environment
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  eks_node_security_group_id = module.eks.node_security_group_id
  instance_class             = var.db_instance_class
  storage_gb                 = var.db_storage_gb
  db_name                    = var.db_name
  db_username                = var.db_username
  db_password                = var.db_password
  multi_az                   = var.db_multi_az
}

# ECR
module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
}

# Timestream for InfluxDB (K-line time-series storage)
module "timestream" {
  source = "./modules/timestream"

  project_name               = var.project_name
  environment                = var.environment
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  eks_node_security_group_id = module.eks.node_security_group_id
  influxdb_password             = var.influxdb_password
  eks_cluster_security_group_id = module.eks.cluster_security_group_id
  oidc_provider_arn             = module.eks.oidc_provider_arn
  oidc_provider_url          = replace(module.eks.oidc_provider_url, "https://", "")
}

# Frontend (S3 + CloudFront + WAF)
module "frontend" {
  source = "./modules/frontend"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  project_name        = var.project_name
  environment         = var.environment
  acm_certificate_arn = var.acm_certificate_arn
  api_gateway_domain  = var.api_gateway_domain
}
