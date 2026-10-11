"""One TAKCL JVM for the operator's remote management calls."""

import importlib
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, ClassVar

# Only creates trusted configuration XML.
import xml.etree.ElementTree as ET  # nosec B405


_JAVA_OPENS = (
    "java.base/java.io",
    "java.base/java.lang",
    "java.base/java.lang.invoke",
    "java.base/java.lang.ref",
    "java.base/java.lang.reflect",
    "java.base/java.math",
    "java.base/java.net",
    "java.base/java.nio",
    "java.base/java.security",
    "java.base/java.security.cert",
    "java.base/java.util",
    "java.base/java.util.concurrent",
    "java.base/java.util.concurrent.atomic",
    "java.base/java.util.concurrent.locks",
    "java.base/javax.security.auth.x500",
    "java.base/jdk.internal.misc",
    "java.base/sun.nio.ch",
    "java.base/sun.reflect.generics.reflectiveObjects",
    "java.base/sun.security.pkcs",
    "java.base/sun.security.pkcs10",
    "java.base/sun.security.pkcs12",
    "java.base/sun.security.provider",
    "java.base/sun.security.rsa",
    "java.base/sun.security.ssl",
    "java.base/sun.security.tools.keytool",
    "java.base/sun.security.util",
    "java.base/sun.security.x509",
    "java.management/com.sun.jmx.mbeanserver",
    "java.sql/java.sql",
    "jdk.management/com.sun.management.internal",
    "jdk.unsupported/sun.misc",
)
_COMMON = "http://bbn.com/marti/takcl/config/common"
_ADMIN_CN = "integration-tak-admin"


class TakJvmRuntime:
    """Keep Java objects inside one process and serialize management calls."""

    _owner: ClassVar["TakJvmRuntime | None"] = None
    _lock: ClassVar[RLock] = RLock()

    def __init__(self) -> None:
        self.pid = os.getpid()
        self.jar = Path(os.environ.get("TAK_USER_MANAGER_JAR", "/opt/tak/utils/UserManager.jar"))
        self.directory = Path(
            os.environ.get("TAK_RUNTIME_DIR", str(Path(tempfile.gettempdir()) / "takoperator"))
        ).resolve()
        self.host = os.environ.get("TAK_IGNITE_HOST", "tak-ignite")
        self.bind_address = os.environ.get("TAK_IGNITE_BIND_ADDRESS", "127.0.0.1")
        self._helper: Any = None
        self._profile: Any = None
        self._manager: Any = None
        self._ssl: Any = None
        self._role: Any = None
        self._closed = False

    def _configuration(self) -> Path:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        common = ET.Element("TAKCLConfiguration", {"xmlns": "http://bbn.com/marti/takcl/config"})
        for name in ("TemporaryDirectory", "FallbackTemporaryDirectory"):
            ET.SubElement(common, f"{{{_COMMON}}}{name}").text = str(self.directory)
        ET.SubElement(
            common,
            f"{{{_COMMON}}}RunnableTAKServerConfig",
            {
                "modelServerDir": str(self.directory),
                "serverFarmDir": str(self.directory),
                "jarName": "takserver-core.jar",
                "TAKIgniteConfigFile": "TAKIgniteConfig.xml",
                "certificateDirectory": str(self.directory),
                "certToolDirectory": str(self.directory),
            },
        )
        path = self.directory / "TAKCLConfig.xml"
        ET.ElementTree(common).write(path, encoding="UTF-8", xml_declaration=True)
        ignite = ET.Element(
            "TAKIgniteConfiguration",
            {
                "xmlns": "http://bbn.com/marti/xml/config",
                "igniteHost": self.bind_address,
                "igniteMulticast": "false",
                "ignitePoolSize": "2",
                "cacheOffHeapInitialSizeBytes": "16777216",
                "cacheOffHeapMaxSizeBytes": "67108864",
            },
        )
        ET.ElementTree(ignite).write(self.directory / "TAKIgniteConfig.xml", encoding="UTF-8", xml_declaration=True)
        return path

    def start(self) -> None:
        with self._lock:
            if self.pid != os.getpid() or self._closed:
                raise RuntimeError("TAK JVM cannot start after closing or forking")
            if self._manager is not None:
                return
            if TakJvmRuntime._owner is not None and TakJvmRuntime._owner is not self:
                raise RuntimeError("Only one TAK JVM is allowed per process")
            if not self.jar.is_file():
                raise FileNotFoundError(self.jar)
            config = importlib.import_module("jnius_config")
            if config.vm_running:
                raise RuntimeError("Configure TAK before starting the JVM")
            path = self._configuration()
            config.set_classpath(str(self.jar.resolve()))
            config.add_options(
                "-Xmx256m",
                "-XX:ActiveProcessorCount=2",
                "-Djava.net.preferIPv4Stack=true",
                "-DIGNITE_UPDATE_NOTIFIER=false",
                "-DIGNITE_QUIET=true",
                f"-Dcom.bbn.marti.takcl.config.filepath={path}",
                f"-Dcom.bbn.marti.takcl.takIgniteConfigPath={self.directory / 'TAKIgniteConfig.xml'}",
                "-Dcom.bbn.marti.takcl.ignoreCoreConfig=true",
                f"-Dcom.bbn.marti.takcl.igniteIpAddressOverride={self.host}",
                "-Dcom.bbn.marti.takcl.igniteNetworkTimeout=10000",
                "-Dcom.bbn.marti.takcl.igniteClientFailureDetectionTimeout=30000",
                f"-Djava.io.tmpdir={self.directory}",
                f"-Dio.netty.tmpdir={self.directory}",
                f"-Dio.netty.native.workdir={self.directory}",
                *(f"--add-opens={name}=ALL-UNNAMED" for name in _JAVA_OPENS),
            )
            os.environ["IGNITE_WORK_DIR"] = str(self.directory)
            TakJvmRuntime._owner = self
            load = importlib.import_module("jnius").autoclass
            self._helper = load("com.bbn.marti.takcl.TakclIgniteHelper")
            profiles = load("com.bbn.marti.test.shared.data.servers.CLIImmutableServerProfiles")
            builder = load("com.bbn.marti.test.shared.data.servers.MutableServerProfile$Builder")
            self._profile = builder.build(profiles.SERVER_CLI.getServer()).setHost(self.host).setIdentifier("").create()
            self._manager = self._helper.getUserManager(self._profile)
            self._ssl = load("com.bbn.marti.takcl.SSLHelper")
            self._role = load("com.bbn.marti.xml.bindings.Role")

    def check(self) -> None:
        with self._lock:
            if self.pid != os.getpid() or self._manager is None or self._closed:
                raise RuntimeError("TAK JVM is unavailable")
            self._manager.getUserList()

    def register_admin(self, certificate_path: Path) -> None:
        """Register only the dedicated certificate; verify remote state after writes."""
        with self._lock:
            self.check()
            certificate = self._ssl.getCertificate(str(certificate_path))
            certificate.checkValidity()
            if (
                str(self._ssl.getCertificateUserName(certificate)) != _ADMIN_CN
                or certificate.getBasicConstraints() != -1
            ):
                raise ValueError("Invalid TAK integration administrator certificate")
            fingerprint = str(self._ssl.getCertificateFingerprint(certificate))
            current = self._manager.getFirstUser(_ADMIN_CN)
            if current is not None and current.getFingerprint() != fingerprint:
                raise ValueError("TAK integration administrator fingerprint conflict")
            role = current.getRole() if current is not None else None
            if role is None or str(role.value()) != "ROLE_ADMIN":
                try:
                    if current is None:
                        self._manager.addOrUpdateUserFromCertificate(certificate)
                    self._manager.setUserRole(_ADMIN_CN, self._role.ROLE_ADMIN)
                except Exception:
                    self._verify_admin(fingerprint)
                    return
            self._verify_admin(fingerprint)

    def _verify_admin(self, fingerprint: str) -> None:
        try:
            current = self._manager.getFirstUser(_ADMIN_CN)
            if current is not None and current.getFingerprint() == fingerprint:
                role = current.getRole()
                if role is not None and str(role.value()) == "ROLE_ADMIN":
                    return
        except Exception:
            raise RuntimeError("TAK integration administrator registration is unverified") from None
        raise RuntimeError("TAK integration administrator registration is unverified") from None

    def close(self) -> None:
        with self._lock:
            if self.pid != os.getpid():
                raise RuntimeError("TAK JVM cannot be used after forking")
            if self._closed:
                return
            self._closed = True
            if self._helper is not None and self._profile is not None:
                self._helper.closeAssociatedIgniteInstance(self._profile)
