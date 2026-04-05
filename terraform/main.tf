terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── Provider ──────────────────────────────────────────────────────────────────
provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}

# ── Data: Latest Ubuntu 22.04 AMI ─────────────────────────────────────────────
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── Key Pair ──────────────────────────────────────────────────────────────────
resource "aws_key_pair" "aiops_key" {
  key_name   = "aiops-key"
  public_key = file(var.public_key_path)
}

# ── Security Group ────────────────────────────────────────────────────────────
resource "aws_security_group" "aiops_sg" {
  name        = "aiops-platform-sg"
  description = "Security group for Enterprise AIOps Platform"

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # FastAPI
  ingress {
    description = "FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Streamlit Dashboard
  ingress {
    description = "Streamlit"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "aiops-platform-sg"
    Project = "enterprise-aiops"
  }
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────
resource "aws_instance" "aiops_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.aiops_key.key_name
  vpc_security_group_ids = [aws_security_group.aiops_sg.id]

  root_block_device {
    volume_size = 20
    volume_type = "gp2"
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    github_repo  = var.github_repo
    llm_provider = var.llm_provider
    groq_api_key = var.groq_api_key
  })

  tags = {
    Name    = "aiops-platform"
    Project = "enterprise-aiops"
  }
}

# ── Elastic IP (so IP doesn't change on restart) ──────────────────────────────
resource "aws_eip" "aiops_eip" {
  instance = aws_instance.aiops_server.id
  domain   = "vpc"

  tags = {
    Name    = "aiops-platform-eip"
    Project = "enterprise-aiops"
  }
}
