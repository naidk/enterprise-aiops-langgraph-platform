"""
RDS Failover Client — triggers RDS cluster/instance failovers via AWS API.

Provides cluster-level failover (Aurora), instance-level forced reboot failover,
and cluster status retrieval. All boto3 calls are wrapped in try/except.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RDSFailoverClient:
    """
    Manages RDS cluster and instance failover operations.

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
    """

    def __init__(self, client_factory) -> None:
        self._factory = client_factory

    def failover_cluster(self, cluster_identifier: str) -> dict:
        """
        Trigger an Aurora cluster failover to a read replica.

        Args:
            cluster_identifier: The DB cluster identifier.

        Returns:
            {"success": bool, "cluster": str, "message": str}
        """
        try:
            rds = self._factory.rds()
            response = rds.failover_db_cluster(DBClusterIdentifier=cluster_identifier)
            cluster_info = response.get("DBCluster", {})
            status = cluster_info.get("Status", "unknown")

            logger.info(
                "RDSFailoverClient.failover_cluster: %s — status=%s",
                cluster_identifier, status,
            )
            return {
                "success": True,
                "cluster": cluster_identifier,
                "message": f"Failover initiated for cluster '{cluster_identifier}' — status: {status}",
            }

        except Exception as exc:
            logger.error(
                "RDSFailoverClient.failover_cluster: failed for '%s' — %s",
                cluster_identifier, exc,
            )
            return {
                "success": False,
                "cluster": cluster_identifier,
                "error": str(exc),
            }

    def failover_instance(self, db_instance_identifier: str) -> dict:
        """
        Force a failover by rebooting an RDS instance with ForceFailover=True.

        Args:
            db_instance_identifier: The DB instance identifier.

        Returns:
            {"success": bool, "instance": str, "message": str}
        """
        try:
            rds = self._factory.rds()
            response = rds.reboot_db_instance(
                DBInstanceIdentifier=db_instance_identifier,
                ForceFailover=True,
            )
            instance_info = response.get("DBInstance", {})
            status = instance_info.get("DBInstanceStatus", "unknown")

            logger.info(
                "RDSFailoverClient.failover_instance: %s — status=%s",
                db_instance_identifier, status,
            )
            return {
                "success": True,
                "instance": db_instance_identifier,
                "message": (
                    f"Force-failover reboot initiated for instance "
                    f"'{db_instance_identifier}' — status: {status}"
                ),
            }

        except Exception as exc:
            logger.error(
                "RDSFailoverClient.failover_instance: failed for '%s' — %s",
                db_instance_identifier, exc,
            )
            return {
                "success": False,
                "instance": db_instance_identifier,
                "error": str(exc),
            }

    def get_cluster_status(self, cluster_identifier: str) -> dict:
        """
        Return the current status of an Aurora DB cluster.

        Returns:
            {"status": str, "endpoint": str, "reader_endpoint": str, "multi_az": bool}
        """
        try:
            rds = self._factory.rds()
            response = rds.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            clusters = response.get("DBClusters", [])

            if not clusters:
                return {
                    "status": "NOT_FOUND",
                    "endpoint": "",
                    "reader_endpoint": "",
                    "multi_az": False,
                    "error": f"Cluster '{cluster_identifier}' not found",
                }

            cluster = clusters[0]
            return {
                "status": cluster.get("Status", "unknown"),
                "endpoint": cluster.get("Endpoint", ""),
                "reader_endpoint": cluster.get("ReaderEndpoint", ""),
                "multi_az": cluster.get("MultiAZ", False),
            }

        except Exception as exc:
            logger.error(
                "RDSFailoverClient.get_cluster_status: failed for '%s' — %s",
                cluster_identifier, exc,
            )
            return {
                "status": "error",
                "endpoint": "",
                "reader_endpoint": "",
                "multi_az": False,
                "error": str(exc),
            }
