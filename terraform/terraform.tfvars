project_name = "zenalpha"
environment  = "prod"
region       = "us-west-2"

eks_node_instance_type = "t3.medium"
eks_node_count         = 1
eks_node_min           = 1
eks_node_max           = 1

db_instance_class = "db.t3.micro"
db_name           = "zenalpha"
db_username       = "zenalpha_admin"
db_multi_az       = false
db_storage_gb     = 20

domain_name         = ""
acm_certificate_arn = ""
api_gateway_domain  = "aaed965d9d5e84599ae69376dbd3b534-fa58da08fef15371.elb.us-west-2.amazonaws.com"
