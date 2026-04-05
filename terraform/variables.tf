variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "aws_access_key" {
  description = "AWS Access Key ID"
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}

variable "instance_type" {
  description = "EC2 instance type (t2.micro = free tier)"
  type        = string
  default     = "t2.micro"
}

variable "public_key_path" {
  description = "Path to your SSH public key file (e.g. ~/.ssh/id_rsa.pub)"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "github_repo" {
  description = "GitHub repo URL to clone (e.g. https://github.com/naidk/enterprise-aiops-langgraph-platform)"
  type        = string
  default     = "https://github.com/naidk/enterprise-aiops-langgraph-platform"
}

variable "llm_provider" {
  description = "LLM provider: mock | groq | anthropic"
  type        = string
  default     = "mock"
}

variable "groq_api_key" {
  description = "Groq API key (leave empty if using mock)"
  type        = string
  sensitive   = true
  default     = ""
}
