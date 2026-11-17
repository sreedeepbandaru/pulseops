# PulseOps on AWS — Terraform
# Creates: VPC + public subnet + internet gateway, security group,
# ECR repos (web + worker), one EC2 server (t3.small, Amazon Linux 2023),
# an IAM role so EC2 can pull from ECR, an S3 bucket for artifacts/logs,
# and a CloudWatch log group.
# NO EKS is used here — EKS alone costs ~$70/month. One EC2 server is
# enough for this project and costs ~$15/month.
# DO NOT run `terraform apply` until you have read terraform/README.md
# and set a billing budget. Run `terraform destroy` when you are done.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Network: one VPC, one public subnet -----------------------------------
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.project_name}-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# --- Security group: SSH only from your IP, web open to the world ----------
resource "aws_security_group" "web" {
  name        = "${var.project_name}-sg"
  description = "PulseOps: SSH from my IP only, web on 80/443/5000"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }
  ingress {
    description = "HTTP (nginx)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Flask direct (debug only)"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project_name}-sg" }
}

# --- ECR: where the CI pipeline pushes the Docker images --------------------
resource "aws_ecr_repository" "web" {
  name                 = "${var.project_name}-web"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = { Name = "${var.project_name}-web" }
}

resource "aws_ecr_repository" "worker" {
  name                 = "${var.project_name}-worker"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = { Name = "${var.project_name}-worker" }
}

# --- IAM: let the EC2 server pull images from ECR (no keys on the server) --
resource "aws_iam_role" "ec2" {
  name = "${var.project_name}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}

# --- EC2: the server that runs the app --------------------------------------
# Amazon Linux 2023, latest AMI in this region.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_name != "" ? var.key_name : null

  # On first boot: install Docker + Compose, create /opt/pulseops,
  # and leave a compose file there for the pipeline to use.
  # The pipeline (GitHub Actions) later pulls the real images and
  # starts the stack. This user_data only prepares the server.
  user_data = <<-EOF
    #!/bin/bash
    set -e
    dnf update -y
    dnf install -y docker git
    systemctl enable --now docker
    usermod -aG docker ec2-user || true
    mkdir -p /opt/pulseops
    # Docker Compose v2 (standalone binary)
    curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    # Log to CloudWatch via the agent is optional; basic logs go to /var/log/cloud-init-output.log
    echo "PulseOps server ready" > /opt/pulseops/README.txt
  EOF

  tags = { Name = "${var.project_name}-ec2" }
}

# --- S3: deploy artifacts / logs (versioned, private) -----------------------
resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${var.project_name}-artifacts-"
  tags          = { Name = "${var.project_name}-artifacts" }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- CloudWatch: one log group for the app ----------------------------------
resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.project_name}/app"
  retention_in_days = 14
  tags              = { Name = "${var.project_name}-logs" }
}
