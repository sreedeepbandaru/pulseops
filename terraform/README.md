# Terraform — PulseOps on AWS

This folder creates the AWS side of PulseOps: VPC, EC2, ECR, S3, CloudWatch.
It does **not** create EKS (Kubernetes on AWS) — EKS alone costs ~$70/month.
One EC2 server is enough here.

## Cost warning — read first
- EC2 t3.small: ~$15/month, plus a small EBS disk charge (~$1–2/month).
- ECR, S3, CloudWatch log group: pennies at this scale.
- **Total while running: roughly $16–18/month. Run `terraform destroy` when you are done, or it keeps charging every month.**
- Set a $10 billing budget in the AWS Console FIRST (see the main README, Step 4).

## Files
- `main.tf` — everything: VPC, subnet, internet gateway, security group, ECR x2, IAM role, EC2, S3, CloudWatch.
- `variables.tf` — region (us-east-1), project name, your IP for SSH, instance type, key pair name.
- `outputs.tf` — EC2 public IP, ECR URLs, live URL. Shown after apply.
- `terraform.tfvars.example` — copy to `terraform.tfvars`, fill in your IP.

## Commands (run in this folder, on your laptop)
```bash
terraform init        # download the AWS provider, once
terraform fmt         # tidy the files
terraform validate    # check the files are valid (no AWS needed)
terraform plan        # show what would be created — read it, no money spent yet
terraform apply       # actually create it — type yes. Costs money from now on.
terraform output      # show the EC2 IP + ECR URLs again
terraform destroy     # DELETE everything — type yes. Stops the charges.
```

## After apply
1. Copy `ec2_public_ip` into GitHub Secrets as `EC2_HOST`.
2. Copy the two ECR URLs — the pipeline uses them via the ECR login step.
3. SSH in to check Docker: `ssh -i your-key.pem ec2-user@<EC2-IP>` then `docker --version` and `ls /opt/pulseops`.
4. The first real deploy happens from GitHub Actions (push to main), not from Terraform. Terraform only prepares the server.

## If apply fails
- "InvalidClientTokenId" — your `aws configure` keys are wrong or expired.
- "Your IP is not allowed" for SSH — your `my_ip` in terraform.tfvars is wrong. Get your IP from https://checkip.amazonaws.com and add `/32`.
- "Limit exceeded" — AWS free-tier / new-account limits. Wait, or ask AWS to raise the limit.
