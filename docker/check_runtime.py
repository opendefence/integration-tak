"""Check the API boundary or the native operator runtime."""

import argparse
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys

EXPECTED_JAR_SHA256 = "329c3831d0550bef309a7c77ff29c3b398279f973bc9789e0db5c26817ac39c7"  # pragma: allowlist secret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=("api", "operator"))
    arguments = parser.parse_args()
    assert sys.version_info[:2] == (3, 14), sys.version
    assert sys.prefix == "/opt/venv", sys.prefix
    importlib.import_module("odintegration_tak.console")
    importlib.import_module("odintegration_tak.packages")
    assert "jnius" not in sys.modules
    for tool in ("javac", "gcc", "uv", "uvx", "pip", "pip3"):
        assert shutil.which(tool) is None, f"Build tool in runtime: {tool}"
    assert importlib.util.find_spec("pip") is None

    if arguments.runtime == "api":
        assert importlib.util.find_spec("jnius") is None
        assert importlib.util.find_spec("jnius_config") is None
        assert shutil.which("java") is None
        assert not Path("/opt/java").exists()
        assert not Path("/opt/tak").exists()
        print("API: Python 3.14; no JVM, JNI, TAK artifacts or build tools.")
        return

    jar = Path("/opt/tak/utils/UserManager.jar")
    checksum = hashlib.sha256(jar.read_bytes()).hexdigest()
    assert checksum == EXPECTED_JAR_SHA256, checksum
    assert not (Path(os.environ["JAVA_HOME"]) / "include/jni.h").exists()
    importlib.import_module("cloudcoil.application")
    config = importlib.import_module("jnius_config")
    config.set_classpath(str(jar))
    jnius = importlib.import_module("jnius")
    user = jnius.autoclass("com.bbn.marti.xml.bindings.UserAuthenticationFile$User")()
    user.setIdentifier("runtime-check")
    assert user.getIdentifier() == "runtime-check"
    system = jnius.autoclass("java.lang.System")
    assert system.getProperty("java.specification.version") == "17"
    print(f"TAK: {Path('/opt/tak/version.txt').read_text().strip()}")
    print(f"JRE: {system.getProperty('java.runtime.version')}; JAR SHA-256: {checksum}")
    print("Operator: Python 3.14; native JNI call passed; build tools absent.")


if __name__ == "__main__":
    main()
