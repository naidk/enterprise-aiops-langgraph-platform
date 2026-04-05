"""
ECS Execution Client — manages ECS services via AWS API (no kubectl required).

Provides restart (forceNewDeployment), rollback (previous task definition),
scale, and status operations. All boto3 calls are wrapped in try/except so
failures return structured error dicts rather than exceptions.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ECSExecutionClient:
    """
    Manages ECS services via the AWS API.

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
        cluster: ECS cluster name. Default: "production".
    """

    def __init__(self, client_factory, cluster: str = "production") -> None:
        self._factory = client_factory
        self._cluster = cluster

    def restart_service(self, service: str) -> dict:
        """
        Force a new ECS deployment for the service (rolling restart).

        Returns:
            {"success": bool, "service": str, "deployment_id": str, "message": str}
        """
        try:
            ecs = self._factory.ecs()
            response = ecs.update_service(
                cluster=self._cluster,
                service=service,
                forceNewDeployment=True,
            )
            svc_detail = response.get("service", {})
            deployments = svc_detail.get("deployments", [])
            deployment_id = deployments[0].get("id", "") if deployments else ""

            logger.info(
                "ECSExecutionClient.restart_service: %s — deployment_id=%s",
                service, deployment_id,
            )
            return {
                "success": True,
                "service": service,
                "deployment_id": deployment_id,
                "message": f"Force-new-deployment triggered for '{service}' in cluster '{self._cluster}'",
            }

        except Exception as exc:
            logger.error("ECSExecutionClient.restart_service: failed for '%s' — %s", service, exc)
            return {"success": False, "service": service, "error": str(exc)}

    def rollback_service(self, service: str, task_definition_arn: str = "") -> dict:
        """
        Roll back an ECS service to a previous task definition.

        If task_definition_arn is empty, automatically determines the previous
        revision by decrementing the current revision number by 1.

        Returns:
            {"success": bool, "service": str, "rolled_back_to": str, "message": str}
        """
        try:
            ecs = self._factory.ecs()
            target_task_def = task_definition_arn

            if not target_task_def:
                # Auto-detect previous revision
                describe_response = ecs.describe_services(
                    cluster=self._cluster,
                    services=[service],
                )
                services = describe_response.get("services", [])
                if not services:
                    return {
                        "success": False,
                        "service": service,
                        "error": f"Service '{service}' not found in cluster '{self._cluster}'",
                    }

                current_task_def = services[0].get("taskDefinition", "")
                if not current_task_def:
                    return {
                        "success": False,
                        "service": service,
                        "error": "Could not determine current task definition",
                    }

                # Parse ARN to get family and revision
                # ARN format: arn:aws:ecs:region:account:task-definition/family:revision
                target_task_def = _decrement_task_def_revision(current_task_def)
                if not target_task_def:
                    return {
                        "success": False,
                        "service": service,
                        "error": f"Could not determine previous revision from '{current_task_def}'",
                    }

                logger.info(
                    "ECSExecutionClient.rollback_service: %s — current=%s rolling back to=%s",
                    service, current_task_def, target_task_def,
                )

            response = ecs.update_service(
                cluster=self._cluster,
                service=service,
                taskDefinition=target_task_def,
            )
            svc_detail = response.get("service", {})
            deployments = svc_detail.get("deployments", [])
            deployment_id = deployments[0].get("id", "") if deployments else ""

            logger.info(
                "ECSExecutionClient.rollback_service: %s — rolled back to %s (deployment=%s)",
                service, target_task_def, deployment_id,
            )
            return {
                "success": True,
                "service": service,
                "rolled_back_to": target_task_def,
                "deployment_id": deployment_id,
                "message": f"Rolled back '{service}' to task definition '{target_task_def}'",
            }

        except Exception as exc:
            logger.error("ECSExecutionClient.rollback_service: failed for '%s' — %s", service, exc)
            return {"success": False, "service": service, "error": str(exc)}

    def scale_service(self, service: str, desired_count: int) -> dict:
        """
        Scale an ECS service to the given desired task count.

        Returns:
            {"success": bool, "service": str, "desired_count": int, "message": str}
        """
        try:
            ecs = self._factory.ecs()
            ecs.update_service(
                cluster=self._cluster,
                service=service,
                desiredCount=desired_count,
            )
            logger.info(
                "ECSExecutionClient.scale_service: %s — desired_count=%d",
                service, desired_count,
            )
            return {
                "success": True,
                "service": service,
                "desired_count": desired_count,
                "message": f"Scaled '{service}' to {desired_count} tasks in cluster '{self._cluster}'",
            }

        except Exception as exc:
            logger.error("ECSExecutionClient.scale_service: failed for '%s' — %s", service, exc)
            return {"success": False, "service": service, "error": str(exc)}

    def get_service_status(self, service: str) -> dict:
        """
        Return current ECS service status.

        Returns:
            {"running": int, "desired": int, "pending": int, "task_definition": str, "status": str}
        """
        try:
            ecs = self._factory.ecs()
            response = ecs.describe_services(
                cluster=self._cluster,
                services=[service],
            )
            services = response.get("services", [])
            if not services:
                return {
                    "running": 0,
                    "desired": 0,
                    "pending": 0,
                    "task_definition": "",
                    "status": "NOT_FOUND",
                    "error": f"Service '{service}' not found in cluster '{self._cluster}'",
                }

            svc = services[0]
            return {
                "running": svc.get("runningCount", 0),
                "desired": svc.get("desiredCount", 0),
                "pending": svc.get("pendingCount", 0),
                "task_definition": svc.get("taskDefinition", ""),
                "status": svc.get("status", "UNKNOWN"),
            }

        except Exception as exc:
            logger.error("ECSExecutionClient.get_service_status: failed for '%s' — %s", service, exc)
            return {"success": False, "error": str(exc)}


def _decrement_task_def_revision(task_def_arn: str) -> str | None:
    """
    Given a task definition ARN like
    'arn:aws:ecs:us-east-1:123456789:task-definition/my-service:5'
    return the ARN with revision decremented by 1, e.g.
    'arn:aws:ecs:us-east-1:123456789:task-definition/my-service:4'.

    Returns None if the revision is already 1 or the ARN cannot be parsed.
    """
    if ":" not in task_def_arn:
        return None

    # Handle both short form "family:revision" and full ARN
    last_colon = task_def_arn.rfind(":")
    if last_colon == -1:
        return None

    revision_str = task_def_arn[last_colon + 1:]
    prefix = task_def_arn[:last_colon]

    try:
        revision = int(revision_str)
    except ValueError:
        return None

    if revision <= 1:
        return None

    return f"{prefix}:{revision - 1}"
