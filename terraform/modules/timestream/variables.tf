variable "project_name" {
  type = string
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "eks_node_security_group_id" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "db.influx.medium"
}

variable "storage_gb" {
  type    = number
  default = 20
}

variable "influxdb_username" {
  type    = string
  default = "admin"
}

variable "influxdb_password" {
  type      = string
  sensitive = true
}

variable "eks_cluster_security_group_id" {
  type        = string
  description = "EKS cluster security group ID"
}

variable "oidc_provider_arn" {
  type = string
}

variable "oidc_provider_url" {
  type = string
}
