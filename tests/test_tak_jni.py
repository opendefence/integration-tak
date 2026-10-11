"""Check the JNI boundary without starting a JVM."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Parses only generated test configuration.
import xml.etree.ElementTree as ET  # nosec B405

import pytest

from opendefence_integration_tak import tak_jni
from opendefence_integration_tak.certificates import PublicCredential

USER_UID = "a942187e-bb81-4b1f-bdcb-6640a460a520"


def native_user() -> MagicMock:
    user = MagicMock()
    for field in ("Identifier", "Fingerprint", "Password", "Role"):
        getter = getattr(user, "get" + field)
        getter.return_value = None

        def assign(value: Any, target: Any = getter) -> None:
            target.return_value = value

        getattr(user, "set" + field).side_effect = assign
    for field in ("GroupList", "GroupListIN", "GroupListOUT"):
        values: list[str] = []
        collection = getattr(user, "get" + field).return_value
        collection.toArray.side_effect = lambda target=values: list(target)
        collection.add.side_effect = values.append
    return user


@pytest.fixture
def native_runtime() -> tuple[tak_jni.TakJvmRuntime, dict[str, Any]]:
    runtime = tak_jni.TakJvmRuntime()
    users: dict[str, Any] = {}
    manager = MagicMock()
    manager.getFirstUser.side_effect = users.get
    manager.getAllUsers.return_value.toArray.side_effect = lambda: list(users.values())
    manager.removeUser.side_effect = users.pop

    def save(user: Any, hashed: bool, previous: Any) -> None:
        assert hashed and previous is users.get(user.getIdentifier())
        users[user.getIdentifier()] = user

    def role(value: str) -> MagicMock:
        result = MagicMock()
        result.value.return_value = value
        return result

    manager.addOrUpdateUser.side_effect = save
    runtime._manager = manager
    runtime._user = native_user
    runtime._role = MagicMock()
    runtime._role.fromValue.side_effect = role
    return runtime, users


def credentials() -> tuple[PublicCredential, PublicCredential]:
    now = datetime.now(UTC)
    first = PublicCredential("a" * 64, "1", "issuer-sha256:" + "b" * 64, now, now + timedelta(days=1))
    return first, replace(first, fingerprint_sha256="c" * 64, serial_hex="2")


def test_native_permissions_rollover_and_revocation(
    native_runtime: tuple[tak_jni.TakJvmRuntime, dict[str, Any]],
) -> None:
    runtime, users = native_runtime
    first, second = credentials()
    foreign = native_user()
    foreign.setIdentifier("integration-tak-admin")
    users["integration-tak-admin"] = foreign
    runtime.reconcile_user(USER_UID, (first, second), "ROLE_ADMIN", ("team",))
    assert len(users) == 3
    runtime.reconcile_user(USER_UID, (first, second), "ROLE_ADMIN", ("team",))
    assert runtime._manager.addOrUpdateUser.call_count == 2
    for fingerprint in ("a", "c"):
        user = users[f"od-user-{USER_UID}-{fingerprint * 64}"]
        assert user.getFingerprint() == ":".join([fingerprint.upper() * 2] * 32)
        assert user.getRole().value() == "ROLE_ADMIN"
        assert user.getGroupList().toArray() == ["team"]
    users[f"od-user-{USER_UID}-{'a' * 64}"].getGroupListIN().add("old-directional")
    runtime.reconcile_user(USER_UID, (first, second), "ROLE_READONLY", ())
    for user in list(users.values())[1:]:
        assert user.getRole().value() == "ROLE_READONLY"
        assert user.getGroupList().toArray() == user.getGroupListIN().toArray() == []
    runtime.reconcile_user(USER_UID, (second,), "ROLE_READONLY", ())
    assert set(users) == {"integration-tak-admin", f"od-user-{USER_UID}-{'c' * 64}"}
    runtime.reconcile_user(USER_UID, (), None, ())
    assert users == {"integration-tak-admin": foreign}


def test_native_partial_writes_recover_by_readback(
    native_runtime: tuple[tak_jni.TakJvmRuntime, dict[str, Any]],
) -> None:
    runtime, users = native_runtime
    first, _ = credentials()

    def persisted(user: Any, _hashed: bool, _previous: Any) -> None:
        users[user.getIdentifier()] = user
        raise RuntimeError("reply lost")

    runtime._manager.addOrUpdateUser.side_effect = persisted
    runtime.reconcile_user(USER_UID, (first,), "ROLE_ADMIN", ())
    runtime._manager.addOrUpdateUser.side_effect = RuntimeError("write lost")
    with pytest.raises(RuntimeError, match="unverified"):
        runtime.reconcile_user(USER_UID, (first,), "ROLE_READONLY", ())
    restarted = tak_jni.TakJvmRuntime()
    restarted._manager = runtime._manager
    restarted.reconcile_user(USER_UID, (), None, ())
    assert users == {}


def test_native_conflicts_and_failed_removal(native_runtime: tuple[tak_jni.TakJvmRuntime, dict[str, Any]]) -> None:
    runtime, users = native_runtime
    first, _ = credentials()
    runtime.reconcile_user(USER_UID, (first,), "ROLE_READONLY", ())
    user = next(iter(users.values()))
    user.setPassword("foreign-password")
    with pytest.raises(ValueError, match="ownership conflict"):
        runtime.reconcile_user(USER_UID, (), None, ())
    runtime._manager.removeUser.assert_not_called()
    user.setPassword(None)
    runtime._manager.removeUser.side_effect = RuntimeError("write lost")
    with pytest.raises(RuntimeError, match="unverified"):
        runtime.reconcile_user(USER_UID, (), None, ())
    assert len(users) == 1


def test_start_configures_one_jvm_and_closes_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    jar = tmp_path / "UserManager.jar"
    jar.touch()
    monkeypatch.setenv("TAK_USER_MANAGER_JAR", str(jar))
    monkeypatch.setenv("TAK_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("TAK_IGNITE_HOST", "tak-ignite")
    monkeypatch.setenv("TAK_IGNITE_BIND_ADDRESS", "10.0.0.4")
    config = MagicMock(vm_running=False)
    java = MagicMock()
    classes: dict[str, MagicMock] = {}

    def load(name: str) -> MagicMock:
        return classes.setdefault(name, MagicMock())

    java.autoclass.side_effect = load
    monkeypatch.setattr(tak_jni.importlib, "import_module", {"jnius_config": config, "jnius": java}.__getitem__)
    monkeypatch.setattr(tak_jni.TakJvmRuntime, "_owner", None)
    runtime = tak_jni.TakJvmRuntime()
    runtime.start()
    runtime.start()
    runtime.check()
    assert ET.parse(tmp_path / "runtime/TAKIgniteConfig.xml").getroot().attrib["igniteHost"] == "10.0.0.4"  # nosec B314
    assert "-Dcom.bbn.marti.takcl.igniteIpAddressOverride=tak-ignite" in config.add_options.call_args.args
    config.set_classpath.assert_called_once_with(str(jar))
    classes["com.bbn.marti.takcl.TakclIgniteHelper"].getUserManager.return_value.getUserList.assert_called_once()
    with pytest.raises(RuntimeError, match="Only one"):
        tak_jni.TakJvmRuntime().start()
    runtime.close()
    classes["com.bbn.marti.takcl.TakclIgniteHelper"].closeAssociatedIgniteInstance.assert_called_once()


def test_register_admin_checks_identity_conflict_and_readback(tmp_path: Path) -> None:
    runtime = tak_jni.TakJvmRuntime()
    manager = MagicMock()
    certificate = MagicMock()
    certificate.getBasicConstraints.return_value = -1
    ssl = MagicMock()
    ssl.getCertificate.return_value = certificate
    ssl.getCertificateUserName.return_value = "integration-tak-admin"
    ssl.getCertificateFingerprint.return_value = "fingerprint"
    runtime._manager = manager
    runtime._ssl = ssl
    runtime._role = MagicMock()
    admin = MagicMock()
    admin.getFingerprint.return_value = "fingerprint"
    admin.getRole.return_value.value.return_value = "ROLE_ADMIN"
    manager.getFirstUser.side_effect = [None, admin, admin]
    runtime.register_admin(tmp_path / "tls.crt")
    manager.addOrUpdateUserFromCertificate.assert_called_once_with(certificate)
    manager.setUserRole.assert_called_once_with("integration-tak-admin", runtime._role.ROLE_ADMIN)

    manager.getFirstUser.side_effect = None
    manager.getFirstUser.return_value = admin
    admin.getFingerprint.return_value = "other"
    with pytest.raises(ValueError, match="fingerprint conflict"):
        runtime.register_admin(tmp_path / "tls.crt")
    ssl.getCertificateUserName.return_value = "someone-else"
    with pytest.raises(ValueError, match="Invalid"):
        runtime.register_admin(tmp_path / "tls.crt")


def test_uncertain_admin_write_requires_readback(tmp_path: Path) -> None:
    runtime = tak_jni.TakJvmRuntime()
    manager = MagicMock()
    runtime._manager = manager
    runtime._ssl = MagicMock()
    runtime._role = MagicMock()
    runtime._ssl.getCertificateUserName.return_value = "integration-tak-admin"
    runtime._ssl.getCertificateFingerprint.return_value = "fingerprint"
    runtime._ssl.getCertificate.return_value.getBasicConstraints.return_value = -1
    manager.getFirstUser.return_value = None
    manager.addOrUpdateUserFromCertificate.side_effect = RuntimeError("lost reply")
    with pytest.raises(RuntimeError, match="unverified"):
        runtime.register_admin(tmp_path / "tls.crt")
