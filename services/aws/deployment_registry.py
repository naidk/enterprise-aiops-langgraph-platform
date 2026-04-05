"""
ECS Deployment Registry — tracks ECS task definitions as the source of truth
for current and previous deployments.

Uses ECS task definition revision numbers to determine rollback targets.
No external state store is required — ECS itself tracks all revisions.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ECSDeploymentRegistry:
    """
    Tracks deployments using ECS task definitions (the real AWS source of truth).

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
        cluster: ECS cluster name. Default: "production".
    """

    def __init__(self, client_factory, cluster: str = "production") -> None:
        self._factory = client_factory
        self._cluster = cluster

    def get_current_task_def(self, service: str) -> str | None:
        """
        Return the current task definition ARN for an ECS service.

        Returns:
            Full task definition ARN string, or None on failure.
        """
        try:
            ecs = self._factory.ecs()
            response = ecs.describe_services(
                cluster=self._cluster,
                services=[service],
            )
            services = response.get("services", [])
            if not services:
                logger.warning(
                    "ECSDeploymentRegistry.get_current_task_def: service '%s' not found in cluster '%s'",
                    service, self._cluster,
                )
                return None

            task_def = services[0].get("taskDefinition", "")
            if task_def:
                logger.debug(
                    "ECSDeploymentRegistry.get_current_task_def: %s → %s",
                    service, task_def,
                )
                return task_def
            return None

        except Exception as exc:
            logger.error(
                "ECSDeploymentRegistry.get_current_task_def: failed for '%s' — %s",
                service, exc,
            )
            return None

    def get_previous_task_def(self, service: str) -> str | None:
        """
        Return the previous task definition ARN (current revision - 1).

        Validates that the previous revision exists in ECS before returning it.

        Returns:
            Previous task definition ARN, or None if no previous revision exists.
        """
        current_arn = self.get_current_task_def(service)
        if not current_arn:
            return None

        previous_arn = _decrement_task_def_revision(current_arn)
        if not previous_arn:
            logger.info(
                "ECSDeploymentRegistry.get_previous_task_def: no previous revision available for '%s' (current=%s)",
                service, current_arn,
            )
            return None

        # Validate that the previous revision actually exists
        try:
            ecs = self._factory.ecs()
            ecs.describe_task_definition(taskDefinition=previous_arn)
            logger.info(
                "ECSDeploymentRegistry.get_previous_task_def: %s → previous=%s",
                service, previous_arn,
            )
            return previous_arn

        except Exception as exc:
            exc_name = type(exc).__name__
            if "ClientException" in exc_name or "InvalidParameterException" in exc_name:
                logger.warning(
                    "ECSDeploymentRegistry.get_previous_task_def: previous revision '%s' not found — %s",
                    previous_arn, exc,
                )
            else:
                logger.error(
                    "ECSDeploymentRegistry.get_previous_task_def: failed to validate '%s' — %s",
                    previous_arn, exc,
                )
            return None

    def get_rollback_info(self, service: str) -> dict:
        """
        Return rollback information for a service.

        Returns:
            {
                "current": str | None,
                "rollback_target": str | None,
                "rollback_command": str
            }
        """
        try:
            current = self.get_current_task_def(service)
            rollback_target = self.get_previous_task_def(service)

            info = {
                "current": current,
                "rollback_target": rollback_target,
                "rollback_command": "ECS API (no kubectl needed)",
            }

            logger.info(
                "ECSDeploymentRegistry.get_rollback_info: %s — current=%s rollback_target=%s",
                service, current, rollback_target,
            )
            return info

        except Exception as exc:
            logger.error(
                "ECSDeploymentRegistry.get_rollback_info: failed for '%s' — %s",
                service, exc,
            )
            return {
                "current": None,
                "rollback_target": None,
                "rollback_command": "ECS API (no kubectl needed)",
                "error": str(exc),
            }


def _decrement_task_def_revision(task_def_arn: str) -> str | None:
    """
    Given a task definition ARN like
    'arn:aws:ecs:us-east-1:123456789:task-definition/my-service:5'
    return the ARN with revision decremented by 1:
    'arn:aws:ecs:us-east-1:123456789:task-definition/my-service:4'.

    Returns None if the revision is already 1 or the ARN cannot be parsed.
    """
    if not task_def_arn or ":" not in task_def_arn:
        return None

    last_colon = task_def_arn.rfind(":")
    revision_str = task_def_arn[last_colon + 1:]
    prefix = task_def_arn[:last_colon]

    try:
        revision = int(revision_str)
    except ValueError:
        return None

    if revision <= 1:
        return None

    return f"{prefix}:{revision - 1}"
