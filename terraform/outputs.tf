output "instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.aiops_server.id
}

output "public_ip" {
  description = "Public IP of the server"
  value       = aws_eip.aiops_eip.public_ip
}

output "api_url" {
  description = "FastAPI base URL"
  value       = "http://${aws_eip.aiops_eip.public_ip}:8000"
}

output "api_docs_url" {
  description = "Swagger UI / API Docs"
  value       = "http://${aws_eip.aiops_eip.public_ip}:8000/docs"
}

output "dashboard_url" {
  description = "Streamlit Dashboard URL"
  value       = "http://${aws_eip.aiops_eip.public_ip}:8501"
}

output "health_check_url" {
  description = "Health check endpoint"
  value       = "http://${aws_eip.aiops_eip.public_ip}:8000/api/v1/health"
}

output "ssh_command" {
  description = "SSH command to connect to server"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.aiops_eip.public_ip}"
}
