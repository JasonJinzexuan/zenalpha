output "endpoint" {
  value       = aws_timestreaminfluxdb_db_instance.main.endpoint
  description = "InfluxDB API endpoint (host:8086)"
}

output "influx_auth_secret_arn" {
  value       = aws_timestreaminfluxdb_db_instance.main.influx_auth_parameters_secret_arn
  description = "Secrets Manager ARN containing operator token"
}

output "agent_role_arn" {
  value = aws_iam_role.agent_timestream.arn
}
