"""Check the legacy JNI disconnect boundary without starting a JVM."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

from cryptography.hazmat.primitives import hashes, serialization
import pytest

from opendefence_integration_tak import subscriptions
from opendefence_integration_tak.subscriptions import Connection, Identity, SubscriptionBackend
from tests.conftest import CredentialFixture


def subscription(node: str, uid: str = "tls:1") -> Mock:
    sub = Mock(uid=uid)
    sub.originNode.toString.return_value = node
    sub.getConnectionId.return_value = "connection-" + node
    return sub


@pytest.fixture
def backend() -> SubscriptionBackend:
    classes: dict[str, Any] = {}
    java = MagicMock()

    def load(name: str) -> Any:
        return classes.setdefault(name, MagicMock())

    def cast(_interface: str, value: Any) -> Any:
        return value

    java.autoclass.side_effect = load
    java.cast.side_effect = cast
    with patch.object(subscriptions.importlib, "import_module", return_value=java):
        result = SubscriptionBackend()
    nodes = [Mock(), Mock()]
    for node, name in zip(nodes, ("node-a", "node-b"), strict=True):
        node.id.return_value.toString.return_value = name
    result._group().nodes().toArray.return_value = nodes
    result._group().forNodeId.return_value.nodes.return_value.isEmpty.return_value = False
    return result


def test_initial_subscription_without_identity_is_deferred() -> None:
    sub = subscription("node-a")
    assert subscriptions.connection_from_subscription(sub) == Connection("node-a", "tls:1", "connection-node-a")
    sub.getConnectionId.return_value = None
    assert subscriptions.connection_from_subscription(sub) is None
    sub.getConnectionId.return_value = "connection"
    sub.originNode = None
    assert subscriptions.connection_from_subscription(sub) is None
    sub.uid = "websocket:1"
    assert subscriptions.connection_from_subscription(sub) is None


def test_service_uses_origin_node_and_bounded_rpc(backend: SubscriptionBackend) -> None:
    proxy = backend._subscriptions("node-a")
    assert backend._subscriptions("node-a") is proxy
    backend._group().forNodeId.assert_called_with(backend.autoclass("java.util.UUID").fromString.return_value)
    backend.autoclass("java.util.UUID").fromString.assert_called_once_with("node-a")
    backend.ignite.services.return_value.serviceProxy.assert_called_once_with(
        backend.constants.DISTRIBUTED_SUBSCRIPTION_MANAGER,
        backend.autoclass("java.lang.ClassLoader").getSystemClassLoader.return_value.loadClass.return_value,
        False,
        5000,
    )
    backend._group().forNodeId.return_value.nodes.return_value.isEmpty.return_value = True
    with pytest.raises(ConnectionError, match="left the cluster"):
        backend._subscriptions("departed")


def test_identity_uses_peer_certificate_and_exact_registration(
    backend: SubscriptionBackend, material: CredentialFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, users = Mock(), Mock()
    services = {
        backend.constants.DISTRIBUTED_GROUP_MANAGER: groups,
        backend.constants.DISTRIBUTED_USER_FILE_MANAGER: users,
    }

    def service(_node: str, _interface: str, name: str) -> Mock:
        return services[name]

    monkeypatch.setattr(backend, "_service", service)
    user = groups.getUserByConnectionId.return_value
    user.getCert.return_value.getEncoded.return_value = material.leaf.public_bytes(serialization.Encoding.DER)
    fingerprint = material.leaf.fingerprint(hashes.SHA256()).hex()
    entry = Mock()
    entry.getFingerprint.return_value = ":".join(fingerprint[i : i + 2] for i in range(0, 64, 2)).upper()
    users.getUserAuthenticationFile.return_value.getUser.return_value.toArray.return_value = [entry]
    connection = Connection("node-a", "tls:1", "server-connection")
    assert backend.identity(connection) == Identity(fingerprint, material.leaf.not_valid_after_utc.timestamp(), True)
    groups.getUserByConnectionId.assert_called_once_with("server-connection")
    # A matching CN or username must not substitute for the certificate fingerprint.
    entry.getFingerprint.return_value = "00:11"
    assert backend.identity(connection) == Identity(fingerprint, material.leaf.not_valid_after_utc.timestamp(), False)
    entry.getFingerprint.return_value = None
    assert backend.identity(connection) == Identity(fingerprint, material.leaf.not_valid_after_utc.timestamp(), False)
    user.getCert.return_value = None
    assert backend.identity(connection) is None
    groups.getUserByConnectionId.return_value = None
    assert backend.identity(connection) is None


def test_guard_preserves_valid_successor_and_retries_reconnects(
    backend: SubscriptionBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = Mock()
    service.getSubscriptionList.return_value.toArray.return_value = [
        subscription("node-a", "tls:" + name) for name in ("valid", "retired", "expired", "refresh", "pending")
    ] + [subscription("node-a", "websocket:1")]
    monkeypatch.setattr(backend, "_subscriptions", Mock(return_value=service))
    identities = {
        "tls:valid": Identity("successor", float("inf"), True),
        "tls:retired": Identity("predecessor", float("inf"), False),
        "tls:expired": Identity("expired", 0, True),
        "tls:refresh": Identity("changed", float("inf"), True),
        "tls:pending": None,
    }

    def identity(connection: Connection) -> Identity | None:
        return identities[connection.uid]

    monkeypatch.setattr(backend, "identity", identity)
    backend._group().nodes().toArray.return_value = backend._group().nodes().toArray.return_value[:1]
    backend.proxies[("departed", "old-service")] = Mock()
    backend.reconcile({"changed"})
    assert [call.args[0] for call in service.deleteSubscription.call_args_list] == [
        "tls:retired",
        "tls:expired",
        "tls:refresh",
    ]
    assert not backend.proxies
    service.deleteSubscription.reset_mock()
    backend.reconcile(set())
    assert [call.args[0] for call in service.deleteSubscription.call_args_list] == ["tls:retired", "tls:expired"]


@pytest.mark.parametrize("failure", ["scan", "identity", "disconnect"])
def test_failed_node_does_not_skip_other_nodes(
    backend: SubscriptionBackend, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    services = {node: Mock() for node in ("node-a", "node-b")}
    for node, service in services.items():
        service.getSubscriptionList.return_value.toArray.return_value = [subscription(node)]
    monkeypatch.setattr(backend, "_subscriptions", services.__getitem__)

    def identity(connection: Connection) -> Identity:
        if failure == "identity" and connection.node == "node-a":
            raise TimeoutError
        return Identity("revoked", float("inf"), False)

    monkeypatch.setattr(backend, "identity", identity)
    if failure == "scan":
        services["node-a"].getSubscriptionList.side_effect = TimeoutError
    elif failure == "disconnect":
        services["node-a"].deleteSubscription.return_value = False
    with pytest.raises(RuntimeError, match="incomplete"):
        backend.reconcile(set())
    services["node-b"].deleteSubscription.assert_called_once_with("tls:1")
    backend._group().nodes().toArray.return_value = []
    with pytest.raises(ConnectionError, match="No TAK messaging nodes"):
        backend.reconcile(set())
