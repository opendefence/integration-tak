"""TAK connection lookup and removal from python-tak-rmapi PR #155.

Source: ed6a8f14656a03d4599aa923d1c7a5901cb0dde7, subscription_jni.py.
The tak-operator owns the JVM and serializes calls with its existing lock.
"""

from dataclasses import dataclass
import importlib
import logging
import time
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Connection:
    """Use identifiers assigned by TAK, never CoT fields supplied by a client."""

    node: str
    uid: str
    connection_id: str


@dataclass(frozen=True)
class Identity:
    fingerprint: str
    expires: float
    registered: bool


def connection_from_subscription(sub: Any) -> Connection | None:
    """Defer initial subscriptions until TAK supplies a TLS connection ID."""
    if not sub.uid.startswith("tls:") or not sub.getConnectionId() or not sub.originNode:
        return None
    return Connection(str(sub.originNode.toString()), str(sub.uid), str(sub.getConnectionId()))


class SubscriptionBackend:
    def __init__(self) -> None:
        java = importlib.import_module("jnius")
        self.autoclass = java.autoclass
        self.cast = java.cast
        self.ignite = self.cast(
            "org.apache.ignite.Ignite", self.autoclass("org.apache.ignite.Ignition").allGrids().get(0)
        )
        self.constants = self.autoclass("tak.server.Constants")
        self.proxies: dict[tuple[str, str], Any] = {}

    def _group(self) -> Any:
        return self.autoclass("com.bbn.cluster.ClusterGroupDefinition").getMessagingClusterDeploymentGroup(self.ignite)

    def _service(self, node: str, interface: str, name: str) -> Any:
        key = (node, name)
        if key not in self.proxies:
            cluster = self._group().forNodeId(self.autoclass("java.util.UUID").fromString(node))
            if cluster.nodes().isEmpty():
                raise ConnectionError("TAK messaging node left the cluster")
            loader = self.autoclass("java.lang.ClassLoader").getSystemClassLoader()
            self.proxies[key] = self.cast(
                interface, self.ignite.services(cluster).serviceProxy(name, loader.loadClass(interface), False, 5000)
            )
        return self.proxies[key]

    def _subscriptions(self, node: str) -> Any:
        return self._service(
            node, "com.bbn.marti.remote.SubscriptionManagerLite", self.constants.DISTRIBUTED_SUBSCRIPTION_MANAGER
        )

    def identity(self, connection: Connection) -> Identity | None:
        """Read the actual TLS certificate through the originating node's GroupManager."""
        groups = self._service(
            connection.node, "com.bbn.marti.remote.groups.GroupManager", self.constants.DISTRIBUTED_GROUP_MANAGER
        )
        user = groups.getUserByConnectionId(connection.connection_id)
        if user is None or user.getCert() is None:
            return None
        certificate = x509.load_der_x509_certificate(bytes(user.getCert().getEncoded()))
        fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        users = self._service(
            connection.node,
            "com.bbn.marti.remote.groups.FileUserManagementInterface",
            self.constants.DISTRIBUTED_USER_FILE_MANAGER,
        )
        registered = any(
            entry.getFingerprint() and entry.getFingerprint().replace(":", "").lower() == fingerprint
            for entry in users.getUserAuthenticationFile().getUser().toArray()
        )
        return Identity(fingerprint, certificate.not_valid_after_utc.timestamp(), registered)

    def disconnect(self, connection: Connection) -> None:
        """Subscription UIDs are local to their originating node."""
        if not self._subscriptions(connection.node).deleteSubscription(connection.uid):
            raise RuntimeError("TAK did not acknowledge subscription removal")

    def reconcile(self, refresh: set[str]) -> None:
        """Refresh changed permissions and remove expired or unregistered identities.

        Attempt the remaining connections and nodes after a failed call.
        The tak-operator retries the full scan after any failure.
        """
        nodes = self._group().nodes().toArray()
        if not len(nodes):
            raise ConnectionError("No TAK messaging nodes available")
        live = {str(node.id().toString()) for node in nodes}
        self.proxies = {key: proxy for key, proxy in self.proxies.items() if key[0] in live}
        failed = False
        for node in sorted(live):
            try:
                subscriptions = self._subscriptions(node).getSubscriptionList().toArray()
            except Exception:
                _LOGGER.warning("TAK subscription scan failed; retry this messaging node")
                failed = True
                continue
            for sub in subscriptions:
                try:
                    connection = connection_from_subscription(sub)
                    if connection is None:
                        continue
                    identity = self.identity(connection)
                    if identity is None:
                        continue
                    if identity.fingerprint in refresh or identity.expires <= time.time() or not identity.registered:
                        self.disconnect(connection)
                except Exception:
                    _LOGGER.warning("TAK connection check failed; retry this subscription")
                    failed = True
        if failed:
            raise RuntimeError("TAK connection reconciliation is incomplete")
