"""
Centralized boto3 client factory for the AIOps platform.

All AWS service clients are created here and cached per factory instance.
Import boto3 lazily (inside methods) so this module can be imported
even when boto3 is not installed — AWS code paths are only entered when
CLOUD_PROVIDER=aws is set.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BotoClientFactory:
    """
    Factory that creates and caches boto3 clients for AWS services.

    Supports three credential modes (in priority order):
    1. Role assumption via STS (role_arn provided)
    2. Explicit key/secret (aws_access_key_id / aws_secret_access_key provided)
    3. Environment / instance profile fallback (no keys provided)
    """

    def __init__(
        self,
        region: str,
        aws_access_key_id: str = "",
        aws_secret_access_key: str = "",
        aws_session_token: str = "",
        role_arn: str = "",
    ) -> None:
        self._region = region
        self._access_key = aws_access_key_id
        self._secret_key = aws_secret_access_key
        self._session_token = aws_session_token
        self._role_arn = role_arn

        # Cached clients
        self._cw = None
        self._logs = None
        self._ecs = None
        self._rds = None
        self._elb = None
        self._sns = None
        self._sts = None

        self._session = None

    def _get_session(self):
        """
        Return a boto3 Session.

        If role_arn is set, assumes the role via STS and returns a session
        with temporary credentials. Otherwise returns a session with the
        provided static keys (or falls back to environment / instance profile).
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 not installed — run: pip install boto3"
            )

        if self._session is not None:
            return self._session

        if self._role_arn:
            # Assume IAM role and use temporary credentials
            try:
                base_session = boto3.Session(
                    aws_access_key_id=self._access_key or None,
                    aws_secret_access_key=self._secret_key or None,
                    aws_session_token=self._session_token or None,
                    region_name=self._region,
                )
                sts = base_session.client("sts")
                response = sts.assume_role(
                    RoleArn=self._role_arn,
                    RoleSessionName="AIOpsAssumedRole",
                )
                creds = response["Credentials"]
                self._session = boto3.Session(
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                    region_name=self._region,
                )
                logger.info("BotoClientFactory: assumed role %s", self._role_arn)
            except Exception as exc:
                logger.error("BotoClientFactory: failed to assume role %s — %s", self._role_arn, exc)
                raise
        else:
            # Use explicit keys or fall back to environment / instance profile
            self._session = boto3.Session(
                aws_access_key_id=self._access_key or None,
                aws_secret_access_key=self._secret_key or None,
                aws_session_token=self._session_token or None,
                region_name=self._region,
            )

        return self._session

    def cloudwatch(self):
        """Return a cached CloudWatch client."""
        if self._cw is None:
            try:
                self._cw = self._get_session().client("cloudwatch", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("cloudwatch", exc)
                raise
        return self._cw

    def logs(self):
        """Return a cached CloudWatch Logs client."""
        if self._logs is None:
            try:
                self._logs = self._get_session().client("logs", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("logs", exc)
                raise
        return self._logs

    def ecs(self):
        """Return a cached ECS client."""
        if self._ecs is None:
            try:
                self._ecs = self._get_session().client("ecs", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("ecs", exc)
                raise
        return self._ecs

    def rds(self):
        """Return a cached RDS client."""
        if self._rds is None:
            try:
                self._rds = self._get_session().client("rds", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("rds", exc)
                raise
        return self._rds

    def elb(self):
        """Return a cached ELBv2 client."""
        if self._elb is None:
            try:
                self._elb = self._get_session().client("elbv2", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("elbv2", exc)
                raise
        return self._elb

    def sns(self):
        """Return a cached SNS client."""
        if self._sns is None:
            try:
                self._sns = self._get_session().client("sns", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("sns", exc)
                raise
        return self._sns

    def sts(self):
        """Return a cached STS client."""
        if self._sts is None:
            try:
                self._sts = self._get_session().client("sts", region_name=self._region)
            except Exception as exc:
                self._handle_client_error("sts", exc)
                raise
        return self._sts

    @staticmethod
    def _handle_client_error(service_name: str, exc: Exception) -> None:
        """Log a user-friendly message for credential/import errors."""
        exc_name = type(exc).__name__
        if "NoCredentialsError" in exc_name:
            logger.error(
                "BotoClientFactory: no AWS credentials found for '%s' client. "
                "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or configure an instance profile.",
                service_name,
            )
        else:
            logger.error("BotoClientFactory: failed to create '%s' client — %s", service_name, exc)
