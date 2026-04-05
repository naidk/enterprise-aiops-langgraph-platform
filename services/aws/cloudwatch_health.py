"""
CloudWatch Health Checker — checks service health via AWS CloudWatch, ECS, and ELB.

Uses the BotoClientFactory to obtain pre-configured boto3 clients.
All methods have try/except wrappers so a single AWS API failure never
crashes the wider AIOps pipeline.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class CloudWatchHealthChecker:
    """
    Checks the health of AWS-hosted services using CloudWatch, ECS, and ELBv2.

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
        ecs_cluster: Name of the ECS cluster to query. Default: "production".
    """

    def __init__(self, client_factory, ecs_cluster: str = "production") -> None:
        self._factory = client_factory
        self._ecs_cluster = ecs_cluster

    def check_service_alarms(self, service: str) -> dict:
        """
        Return CloudWatch alarm states for a given service name prefix.

        Returns:
            {
                "alarm_count": int,
                "in_alarm": int,
                "ok": int,
                "alarms": [{"name": str, "state": str, "reason": str}]
            }
        """
        try:
            cw = self._factory.cloudwatch()
            response = cw.describe_alarms(AlarmNamePrefix=service)
            metric_alarms = response.get("MetricAlarms", [])
            composite_alarms = response.get("CompositeAlarms", [])
            all_alarms = metric_alarms + composite_alarms

            alarm_list = []
            in_alarm_count = 0
            ok_count = 0

            for alarm in all_alarms:
                state = alarm.get("StateValue", "UNKNOWN")
                name = alarm.get("AlarmName", "")
                reason = alarm.get("StateReason", "")

                alarm_list.append({"name": name, "state": state, "reason": reason})

                if state == "ALARM":
                    in_alarm_count += 1
                elif state == "OK":
                    ok_count += 1

            logger.info(
                "CloudWatchHealthChecker.check_service_alarms: %s — total=%d in_alarm=%d ok=%d",
                service, len(alarm_list), in_alarm_count, ok_count,
            )
            return {
                "alarm_count": len(alarm_list),
                "in_alarm": in_alarm_count,
                "ok": ok_count,
                "alarms": alarm_list,
            }

        except Exception as exc:
            logger.error(
                "CloudWatchHealthChecker.check_service_alarms: failed for '%s' — %s",
                service, exc,
            )
            return {
                "alarm_count": 0,
                "in_alarm": 0,
                "ok": 0,
                "alarms": [],
                "error": str(exc),
                "healthy": False,
            }

    def check_ecs_service_health(self, service: str) -> dict:
        """
        Return ECS service health for the given service name.

        A service is considered healthy when:
        - running_count >= desired_count
        - No deployment is in progress (PRIMARY with ACTIVATING/IN_PROGRESS rollout)

        Returns:
            {
                "running_count": int,
                "desired_count": int,
                "pending_count": int,
                "healthy": bool,
                "deployments": [...]
            }
        """
        try:
            ecs = self._factory.ecs()
            response = ecs.describe_services(
                cluster=self._ecs_cluster,
                services=[service],
            )

            services = response.get("services", [])
            if not services:
                logger.warning(
                    "CloudWatchHealthChecker.check_ecs_service_health: service '%s' not found in cluster '%s'",
                    service, self._ecs_cluster,
                )
                return {
                    "running_count": 0,
                    "desired_count": 0,
                    "pending_count": 0,
                    "healthy": False,
                    "deployments": [],
                    "error": f"Service '{service}' not found in cluster '{self._ecs_cluster}'",
                }

            svc = services[0]
            running = svc.get("runningCount", 0)
            desired = svc.get("desiredCount", 0)
            pending = svc.get("pendingCount", 0)
            deployments = svc.get("deployments", [])

            # Detect in-progress deployments
            in_progress = any(
                d.get("rolloutState") in ("IN_PROGRESS", "FAILED")
                for d in deployments
            )

            healthy = (running >= desired) and not in_progress

            deployment_info = [
                {
                    "id": d.get("id", ""),
                    "status": d.get("status", ""),
                    "rollout_state": d.get("rolloutState", ""),
                    "running_count": d.get("runningCount", 0),
                    "desired_count": d.get("desiredCount", 0),
                    "task_definition": d.get("taskDefinition", ""),
                }
                for d in deployments
            ]

            logger.info(
                "CloudWatchHealthChecker.check_ecs_service_health: %s — running=%d desired=%d healthy=%s",
                service, running, desired, healthy,
            )
            return {
                "running_count": running,
                "desired_count": desired,
                "pending_count": pending,
                "healthy": healthy,
                "deployments": deployment_info,
            }

        except Exception as exc:
            logger.error(
                "CloudWatchHealthChecker.check_ecs_service_health: failed for '%s' — %s",
                service, exc,
            )
            return {
                "running_count": 0,
                "desired_count": 0,
                "pending_count": 0,
                "healthy": False,
                "deployments": [],
                "error": str(exc),
            }

    def check_target_group_health(self, service: str, target_group_arn: str) -> dict:
        """
        Return ELBv2 target group health counts.

        Returns:
            {"healthy": int, "unhealthy": int, "total": int}
        """
        try:
            elb = self._factory.elb()
            response = elb.describe_target_health(TargetGroupArn=target_group_arn)
            health_descriptions = response.get("TargetHealthDescriptions", [])

            healthy_count = sum(
                1 for t in health_descriptions
                if t.get("TargetHealth", {}).get("State") == "healthy"
            )
            unhealthy_count = sum(
                1 for t in health_descriptions
                if t.get("TargetHealth", {}).get("State") != "healthy"
            )
            total = len(health_descriptions)

            logger.info(
                "CloudWatchHealthChecker.check_target_group_health: %s — healthy=%d unhealthy=%d total=%d",
                service, healthy_count, unhealthy_count, total,
            )
            return {
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "total": total,
            }

        except Exception as exc:
            logger.error(
                "CloudWatchHealthChecker.check_target_group_health: failed for '%s' — %s",
                service, exc,
            )
            return {
                "healthy": 0,
                "unhealthy": 0,
                "total": 0,
                "error": str(exc),
                "healthy_flag": False,
            }
