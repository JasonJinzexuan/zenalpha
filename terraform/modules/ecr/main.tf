locals {
  repositories = toset([
    "eureka-server",
    "gateway",
    "signal-service",
    "backtest-service",
    "data-service",
    "user-service",
    "notification-service",
    "frontend",
  ])
}

resource "aws_ecr_repository" "repos" {
  for_each = local.repositories

  name                 = "${var.project_name}/${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${each.key}"
  }
}

resource "aws_ecr_lifecycle_policy" "repos" {
  for_each = local.repositories

  repository = aws_ecr_repository.repos[each.key].name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}
