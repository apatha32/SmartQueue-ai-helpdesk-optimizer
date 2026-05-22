output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Run this command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "ecr_api_url" {
  description = "ECR URL for the API image (set as global.imageRegistry in Helm values)"
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_worker_url" {
  description = "ECR URL for the worker image"
  value       = aws_ecr_repository.worker.repository_url
}

output "ecr_registry" {
  description = "Base ECR registry URL (account.dkr.ecr.region.amazonaws.com)"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN secret in your GitHub repository"
  value       = aws_iam_role.github_actions.arn
}

output "lb_controller_role_arn" {
  description = "IRSA role ARN for the AWS Load Balancer Controller"
  value       = module.lb_controller_irsa_role.iam_role_arn
}

data "aws_caller_identity" "current" {}
