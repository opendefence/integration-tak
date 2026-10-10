"""Generated credential fixtures and explicit Java compatibility checks."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import shutil

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
import pytest

from opendefence_integration_tak.certificates import ClientCredential


@dataclass(frozen=True)
class CredentialFixture:
    credential: ClientCredential
    root: x509.Certificate
    intermediate: x509.Certificate
    leaf: x509.Certificate
    now: datetime

    @property
    def trust_pem(self) -> bytes:
        return self.root.public_bytes(serialization.Encoding.PEM) + self.intermediate.public_bytes(
            serialization.Encoding.PEM
        )


@pytest.fixture(scope="session", params=("ec", "rsa"))
def material(request: pytest.FixtureRequest) -> CredentialFixture:
    now = datetime.now(UTC)
    certificates: list[x509.Certificate] = []
    keys = [
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if request.param == "rsa"
        else ec.generate_private_key(ec.SECP256R1())
        for _ in range(3)
    ]
    names = [
        x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, value)])
        for value in ("fixture root", "fixture intermediate", "00000000-0000-4000-8000-000000000001")
    ]
    for index, name in enumerate(names):
        issuer_index = max(0, index - 1)
        certificates.append(
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(names[issuer_index])
            .public_key(keys[index].public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=index < 2, path_length=None), critical=True)
            .sign(keys[issuer_index], hashes.SHA256())
        )
    credential = ClientCredential(
        certificate_chain_pem=b"".join(
            cert.public_bytes(serialization.Encoding.PEM) for cert in reversed(certificates)
        ),
        private_key_pem=keys[-1].private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
        password="fixture-only-password",  # pragma: allowlist secret
        expected_cn="00000000-0000-4000-8000-000000000001",
    )
    return CredentialFixture(credential, certificates[0], certificates[1], certificates[2], now)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--require-keytool", action="store_true", help="Run mandatory Java PKCS#12 compatibility checks")


@pytest.fixture
def keytool(request: pytest.FixtureRequest) -> str:
    if not request.config.getoption("--require-keytool"):
        pytest.skip("Run the package-test image or pass --require-keytool with Java 17 installed")
    executable = shutil.which("keytool")
    if executable is None:
        pytest.fail("--require-keytool needs keytool on PATH")
    return executable
