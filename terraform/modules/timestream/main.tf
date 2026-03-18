# Security group for InfluxDB — allow port 8086 from EKS nodes
resource "aws_security_group" "influxdb" {
  name_prefix = "${var.project_name}-influxdb-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8086
    to_port         = 8086
    protocol        = "tcp"
    security_groups = [var.eks_node_security_group_id, var.eks_cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-influxdb"
    Project     = var.project_name
    Environment = var.environment
  }
}

# Timestream for InfluxDB instance
resource "aws_timestreaminfluxdb_db_instance" "main" {
  name                = "${var.project_name}-influxdb"
  db_instance_type    = var.instance_type
  db_storage_type     = "InfluxIOIncludedT1"
  allocated_storage   = var.storage_gb
  username            = var.influxdb_username
  password            = var.influxdb_password
  organization        = var.project_name
  bucket              = "marketdata"
  deployment_type     = "SINGLE_AZ"
  publicly_accessible = false

  vpc_subnet_ids         = var.private_subnet_ids
  vpc_security_group_ids = [aws_security_group.influxdb.id]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
