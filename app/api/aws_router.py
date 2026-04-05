"""
AWS Integration API Router — FastAPI endpoints for AWS-specific operations.

All endpoints check settings.using_aws first. If CLOUD_PROVIDER != "aws"
they return a 200 with an error message explaining how to enable AWS mode.

Prefix: /api/v1/aws
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/aws", tags=["AWS Integration"])


def _require_aws():
    """
    Return (settings, factory) or raise HTTPException-like dict.
    Returns None for factory if AWS is not enabled.
    """
    from app.config import settings  # local import to avoid circular deps
    return settings


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_factory():
    """Build a BotoClientFactory from current settings."""
    from app.config import settings
    from services.aws.boto_client import BotoClientFactory

    return BotoClientFactory(
        region=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_session_token=settings.aws_session_token,
        role_arn=settings.aws_role_arn,
    )


_AWS_DISABLED_MSG = {
    "error": "Set CLOUD_PROVIDER=aws in .env to enable AWS endpoints"
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", summary="Check AWS connectivity")
async def aws_status() -> dict:
    """
    Verify AWS credentials by calling STS GetCallerIdentity.
    Returns the IAM identity currently in use.
    """
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        factory = _build_factory()
        sts = factory.sts()
        identity = sts.get_caller_identity()
        return {
            "connected": True,
            "account": identity.get("Account", ""),
            "user_id": identity.get("UserId", ""),
            "arn": identity.get("Arn", ""),
            "region": settings.aws_region,
        }
    except Exception as exc:
        logger.error("aws_status: %s", exc)
        return {"connected": False, "error": str(exc)}


@router.get("/ecs/{service}", summary="Get ECS service status")
async def get_ecs_service(service: str) -> dict:
    """Return running/desired task counts and current task definition for an ECS service."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.ecs_execution import ECSExecutionClient
        client = ECSExecutionClient(_build_factory(), cluster=settings.aws_ecs_cluster)
        return client.get_service_status(service)
    except Exception as exc:
        logger.error("get_ecs_service: %s", exc)
        return {"error": str(exc)}


@router.post("/ecs/{service}/restart", summary="Restart ECS service")
async def restart_ecs_service(service: str) -> dict:
    """Force a new ECS deployment (rolling restart) for the specified service."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.ecs_execution import ECSExecutionClient
        client = ECSExecutionClient(_build_factory(), cluster=settings.aws_ecs_cluster)
        return client.restart_service(service)
    except Exception as exc:
        logger.error("restart_ecs_service: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/ecs/{service}/rollback", summary="Rollback ECS service")
async def rollback_ecs_service(service: str) -> dict:
    """Roll back an ECS service to its previous task definition revision."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.ecs_execution import ECSExecutionClient
        client = ECSExecutionClient(_build_factory(), cluster=settings.aws_ecs_cluster)
        return client.rollback_service(service)
    except Exception as exc:
        logger.error("rollback_ecs_service: %s", exc)
        return {"success": False, "error": str(exc)}


@router.get("/logs/{service}", summary="Tail CloudWatch logs for service")
async def get_service_logs(service: str, minutes: int = 10) -> dict:
    """Return the last 50 CloudWatch log events for the specified service."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.cloudwatch_logs import CloudWatchLogsClient
        client = CloudWatchLogsClient(
            _build_factory(),
            log_group_prefix=settings.aws_log_group_prefix,
        )
        logs = client.get_recent_logs(service, minutes=minutes, max_events=50)
        return {"service": service, "log_count": len(logs), "logs": logs}
    except Exception as exc:
        logger.error("get_service_logs: %s", exc)
        return {"error": str(exc)}


@router.get("/alarms/{service}", summary="List CloudWatch alarms for service")
async def get_service_alarms(service: str) -> dict:
    """Return all CloudWatch alarms whose name starts with the service name."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.cloudwatch_health import CloudWatchHealthChecker
        checker = CloudWatchHealthChecker(_build_factory(), ecs_cluster=settings.aws_ecs_cluster)
        return checker.check_service_alarms(service)
    except Exception as exc:
        logger.error("get_service_alarms: %s", exc)
        return {"error": str(exc)}


@router.get("/metrics/{service}", summary="Get CloudWatch metrics for service")
async def get_service_metrics(service: str) -> dict:
    """Return a CloudWatch metrics snapshot (CPU, memory, errors, latency) for a service."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.cloudwatch_metrics import CloudWatchMetricsClient
        client = CloudWatchMetricsClient(
            _build_factory(),
            namespace=settings.aws_cloudwatch_namespace,
        )
        metrics = client.get_service_metrics(service)
        return {"service": service, "metrics": metrics}
    except Exception as exc:
        logger.error("get_service_metrics: %s", exc)
        return {"error": str(exc)}


@router.post("/rds/{cluster_id}/failover", summary="Trigger RDS cluster failover")
async def rds_failover(cluster_id: str) -> dict:
    """Initiate an Aurora DB cluster failover to a read replica."""
    from app.config import settings
    if not settings.using_aws:
        return _AWS_DISABLED_MSG

    try:
        from services.aws.rds_failover import RDSFailoverClient
        client = RDSFailoverClient(_build_factory())
        return client.failover_cluster(cluster_id)
    except Exception as exc:
        logger.error("rds_failover: %s", exc)
        return {"success": False, "error": str(exc)}
