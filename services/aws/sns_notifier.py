"""
SNS Notifier — sends AIOps alerts via AWS Simple Notification Service.

Publishes formatted incident notifications to an SNS topic.
If no topic ARN is configured, logs a warning and returns without publishing.
All boto3 calls are wrapped in try/except.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SNSNotifier:
    """
    Sends AIOps incident notifications via AWS SNS.

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
        topic_arn: SNS topic ARN to publish to. Leave empty to disable publishing.
    """

    def __init__(self, client_factory, topic_arn: str = "") -> None:
        self._factory = client_factory
        self._topic_arn = topic_arn

    def publish(self, subject: str, message: str) -> dict:
        """
        Publish a message to the configured SNS topic.

        Args:
            subject: Email subject line / notification title (max 100 chars).
            message: Full notification body text.

        Returns:
            {"published": True, "message_id": str} on success.
            {"published": False, "reason": str} if no topic ARN.
            {"published": False, "error": str} on AWS failure.
        """
        if not self._topic_arn:
            logger.warning(
                "SNSNotifier.publish: no topic ARN configured — message NOT sent. "
                "Set AWS_SNS_TOPIC_ARN in .env to enable SNS alerts."
            )
            return {"published": False, "reason": "no topic ARN"}

        try:
            sns = self._factory.sns()
            response = sns.publish(
                TopicArn=self._topic_arn,
                Subject=subject[:100],  # SNS subject max is 100 chars
                Message=message,
            )
            message_id = response.get("MessageId", "")
            logger.info(
                "SNSNotifier.publish: message published — message_id=%s subject='%s'",
                message_id, subject,
            )
            return {"published": True, "message_id": message_id}

        except Exception as exc:
            logger.error("SNSNotifier.publish: failed — %s", exc)
            return {"published": False, "error": str(exc)}

    def notify_incident(
        self,
        incident_id: str,
        service: str,
        severity: str,
        summary: str,
    ) -> dict:
        """
        Send a formatted incident alert to the SNS topic.

        Args:
            incident_id: Unique incident identifier.
            service: Affected service name.
            severity: Severity level (e.g. "CRITICAL", "HIGH", "MEDIUM").
            summary: Human-readable incident summary.

        Returns:
            Result dict from publish().
        """
        subject = f"[{severity.upper()}] AIOps Alert: {service}"
        now_iso = datetime.now(timezone.utc).isoformat()

        message_body = (
            f"AIOps Incident Alert\n"
            f"{'=' * 40}\n"
            f"Incident ID : {incident_id}\n"
            f"Service     : {service}\n"
            f"Severity    : {severity.upper()}\n"
            f"Timestamp   : {now_iso}\n"
            f"\nSummary:\n{summary}\n"
        )

        return self.publish(subject=subject, message=message_body)
