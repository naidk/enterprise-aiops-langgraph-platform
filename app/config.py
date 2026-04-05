"""
Application configuration.

All values are driven by environment variables loaded from .env.
Import the `settings` singleton throughout the application — never
instantiate Settings directly.

Usage:
    from app.config import settings
    print(settings.app_name)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (works both locally and in Docker)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("1", "true", "yes")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_list(key: str, default: str = "") -> list[str]:
    raw = _env(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """
    Immutable, environment-driven application settings.
    Resolved once at import time; never mutated at runtime.
    """

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = field(default_factory=lambda: _env("APP_NAME", "Enterprise AIOps Platform"))
    app_version: str = field(default_factory=lambda: _env("APP_VERSION", "1.0.0"))
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", default=False))

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = field(default_factory=lambda: _env("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))
    cors_origins: list[str] = field(default_factory=lambda: _env_list("CORS_ORIGINS", "*"))

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "mock"))
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "llama-3.3-70b-versatile"))
    llm_temperature: float = field(default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.1")))

    # ── Storage ───────────────────────────────────────────────────────────────
    storage_dir: str = field(default_factory=lambda: _env("STORAGE_DIR", "storage"))
    incidents_file: str = field(default_factory=lambda: _env("INCIDENTS_FILE", "storage/incidents.json"))
    audit_log_file: str = field(default_factory=lambda: _env("AUDIT_LOG_FILE", "storage/audit_log.json"))
    metrics_file: str = field(default_factory=lambda: _env("METRICS_FILE", "storage/metrics.json"))

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: _env("LOG_FORMAT", "json"))
    log_dir: str = field(default_factory=lambda: _env("LOG_DIR", "logs"))

    # ── AIOps Behaviour ───────────────────────────────────────────────────────
    auto_remediation_enabled: bool = field(default_factory=lambda: _env_bool("AUTO_REMEDIATION"))
    escalation_threshold: int = field(default_factory=lambda: _env_int("ESCALATION_THRESHOLD", 3))
    max_remediation_retries: int = field(default_factory=lambda: _env_int("MAX_REMEDIATION_RETRIES", 3))
    incident_ttl_days: int = field(default_factory=lambda: _env_int("INCIDENT_TTL_DAYS", 90))

    # ── Jira Integration ──────────────────────────────────────────────────────
    jira_enabled: bool = field(default_factory=lambda: _env_bool("JIRA_ENABLED"))
    jira_base_url: str = field(default_factory=lambda: _env("JIRA_BASE_URL"))
    jira_api_token: str = field(default_factory=lambda: _env("JIRA_API_TOKEN"))
    jira_project_key: str = field(default_factory=lambda: _env("JIRA_PROJECT_KEY", "AIOPS"))
    jira_user_email: str = field(default_factory=lambda: _env("JIRA_USER_EMAIL"))

    # ── Pipeline Simulator ────────────────────────────────────────────────────
    simulator_tick_seconds: int = field(default_factory=lambda: _env_int("SIMULATOR_TICK_SECONDS", 10))
    simulator_failure_rate: float = field(default_factory=lambda: float(_env("SIMULATOR_FAILURE_RATE", "0.15")))

    # ── Stage 4 — Real Execution ──────────────────────────────────────────────
    dry_run_mode: bool = field(default_factory=lambda: _env_bool("DRY_RUN_MODE", default=True))
    execution_timeout_seconds: int = field(default_factory=lambda: _env_int("EXECUTION_TIMEOUT_SECONDS", 300))
    # Health check settings
    health_check_base_url: str = field(default_factory=lambda: _env("HEALTH_CHECK_BASE_URL", "http://localhost:8000"))
    health_check_path: str = field(default_factory=lambda: _env("HEALTH_CHECK_PATH", "/health"))
    health_check_timeout_seconds: int = field(default_factory=lambda: _env_int("HEALTH_CHECK_TIMEOUT_SECONDS", 5))
    health_check_max_wait_seconds: int = field(default_factory=lambda: _env_int("HEALTH_CHECK_MAX_WAIT_SECONDS", 120))
    health_check_interval_seconds: int = field(default_factory=lambda: _env_int("HEALTH_CHECK_INTERVAL_SECONDS", 10))
    # Approval settings
    approval_required: bool = field(default_factory=lambda: _env_bool("APPROVAL_REQUIRED", default=False))
    slack_webhook_url: str = field(default_factory=lambda: _env("SLACK_WEBHOOK_URL", ""))
    approval_timeout_seconds: int = field(default_factory=lambda: _env_int("APPROVAL_TIMEOUT_SECONDS", 300))
    # Deployment tracking
    deployments_file: str = field(default_factory=lambda: _env("DEPLOYMENTS_FILE", "storage/deployments.json"))
    # Circuit breaker
    circuit_breaker_file: str = field(default_factory=lambda: _env("CIRCUIT_BREAKER_FILE", "storage/circuit_breakers.json"))
    circuit_breaker_failure_threshold: int = field(default_factory=lambda: _env_int("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3))
    circuit_breaker_recovery_minutes: int = field(default_factory=lambda: _env_int("CIRCUIT_BREAKER_RECOVERY_MINUTES", 10))

    # ── AWS Integration ────────────────────────────────────────────────────────────
    cloud_provider: str = field(default_factory=lambda: _env("CLOUD_PROVIDER", "local"))
    aws_region: str = field(default_factory=lambda: _env("AWS_REGION", "us-east-1"))
    aws_access_key_id: str = field(default_factory=lambda: _env("AWS_ACCESS_KEY_ID", ""))
    aws_secret_access_key: str = field(default_factory=lambda: _env("AWS_SECRET_ACCESS_KEY", ""))
    aws_session_token: str = field(default_factory=lambda: _env("AWS_SESSION_TOKEN", ""))
    aws_role_arn: str = field(default_factory=lambda: _env("AWS_ROLE_ARN", ""))
    aws_ecs_cluster: str = field(default_factory=lambda: _env("AWS_ECS_CLUSTER", "production"))
    aws_log_group_prefix: str = field(default_factory=lambda: _env("AWS_LOG_GROUP_PREFIX", "/aws/ecs"))
    aws_cloudwatch_namespace: str = field(default_factory=lambda: _env("AWS_CLOUDWATCH_NAMESPACE", "AWS/ECS"))
    aws_rds_cluster_id: str = field(default_factory=lambda: _env("AWS_RDS_CLUSTER_ID", ""))

    # ── GitHub Integration ────────────────────────────────────────────────────
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN", ""))
    github_repo: str = field(default_factory=lambda: _env("GITHUB_REPO", "naidk/enterprise-aiops-langgraph-platform"))

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def using_real_llm(self) -> bool:
        return self.llm_provider != "mock" and any([
            self.anthropic_api_key,
            self.openai_api_key,
            self.groq_api_key
        ])

    @property
    def using_aws(self) -> bool:
        return self.cloud_provider.lower() == "aws"


# Module-level singleton
settings = Settings()
