# Outputs — shown after `terraform apply`. Copy these into GitHub Secrets
# and into your browser to check the live app.
output "ec2_public_ip" {
  description = "Public IP of the EC2 server — open http://<this IP>/ in a browser"
  value       = aws_instance.web.public_ip
}

output "ec2_public_dns" {
  description = "Public DNS name of the EC2 server"
  value       = aws_instance.web.public_dns
}

output "ecr_web_url" {
  description = "ECR repository URL for the web image"
  value       = aws_ecr_repository.web.repository_url
}

output "ecr_worker_url" {
  description = "ECR repository URL for the worker image"
  value       = aws_ecr_repository.worker.repository_url
}

output "s3_artifacts_bucket" {
  description = "S3 bucket for deploy artifacts / logs"
  value       = aws_s3_bucket.artifacts.bucket
}

output "live_url" {
  description = "Live dashboard URL (nginx on port 80)"
  value       = "http://${aws_instance.web.public_ip}/"
}
