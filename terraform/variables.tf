# Terraform variables — change these in terraform.tfvars (see the example file).
# Never put AWS keys in any .tf file. Keys live in `aws configure` / GitHub Secrets.

variable "aws_region" {
  description = "AWS region for everything in this project"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name used as a prefix for all resources"
  type        = string
  default     = "pulseops"
}

variable "my_ip" {
  description = "Your home/office IP in CIDR form, e.g. 203.0.113.10/32 — only this IP can SSH in. Find yours at https://checkip.amazonaws.com"
  type        = string
  default     = "0.0.0.0/0" # CHANGE THIS in terraform.tfvars to your real IP
}

variable "instance_type" {
  description = "EC2 size. t3.small is ~$15/month. Do not use a bigger one unless you need it."
  type        = string
  default     = "t3.small"
}

variable "key_name" {
  description = "Name of an EC2 key pair you created in the AWS Console (EC2 > Key Pairs). Empty = no key pair, use Session Manager instead."
  type        = string
  default     = ""
}
