"""Check the JNI boundary without starting a JVM."""

from pathlib import Path
from unittest.mock import MagicMock

# Parses only generated test configuration.
import xml.etree.ElementTree as ET  # nosec B405

import pytest

from opendefence_integration_tak import tak_jni


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
