"""Bounded PKCS#12 export of existing credentials and public trust anchors."""

from dataclasses import dataclass, field
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

MAX_PEM_BYTES = 1024 * 1024
MAX_CERTIFICATES = 32
MAX_KEY_BYTES = 16 * 1024
# This password protects public certificates only.
TRUSTSTORE_PASSWORD = "public"  # nosec B105  # pragma: allowlist secret


@dataclass(frozen=True, slots=True)
class ClientCredential:
    """Already-issued material; expected CN comes from the authoritative adapter."""

    certificate_chain_pem: bytes = field(repr=False)
    private_key_pem: bytes = field(repr=False)
    password: str = field(repr=False)
    expected_cn: str


def _certificates(pem: bytes) -> list[x509.Certificate]:
    if not 0 < len(pem) <= MAX_PEM_BYTES:
        raise ValueError("Certificate bundle exceeds size limit or is empty")
    certificates = x509.load_pem_x509_certificates(pem)
    if not 0 < len(certificates) <= MAX_CERTIFICATES:
        raise ValueError("Certificate bundle exceeds count limit or is empty")
    return certificates


def _is_ca(certificate: x509.Certificate) -> bool:
    try:
        return certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    except x509.ExtensionNotFound:
        return False


def client_keystore(credential: ClientCredential, *, now: datetime) -> bytes:
    """Export one key and its leaf-first chain. Do not issue or approve credentials."""
    if now.utcoffset() is None:
        raise ValueError("An aware verification time is required")
    password = credential.password
    if not 6 <= len(password) <= 128 or not password.isascii() or not password.isprintable():
        raise ValueError("PKCS#12 password must be 6 to 128 printable ASCII characters")
    certificates = _certificates(credential.certificate_chain_pem)
    leaf = certificates[0]
    names = leaf.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not credential.expected_cn or len(names) != 1 or names[0].value != credential.expected_cn:
        raise ValueError("Client certificate does not match the expected CN")
    if _is_ca(leaf) or not leaf.not_valid_before_utc <= now < leaf.not_valid_after_utc:
        raise ValueError("Client certificate is not a currently valid leaf")
    for child, issuer in zip(certificates, certificates[1:], strict=False):
        if not _is_ca(issuer):
            raise ValueError("Client chain contains a non-CA issuer")
        child.verify_directly_issued_by(issuer)
    if not 0 < len(credential.private_key_pem) <= MAX_KEY_BYTES:
        raise ValueError("Private key exceeds size limit or is empty")
    key = serialization.load_pem_private_key(credential.private_key_pem, password=None)
    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise ValueError("Client export requires an RSA or EC key")
    if key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ) != leaf.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo):
        raise ValueError("Client private key does not match the certificate")
    # The public truststore's legacy encryption must never protect the client key.
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(600_000)
        .key_cert_algorithm(pkcs12.PBES.PBESv2SHA256AndAES256CBC)
        .hmac_hash(hashes.SHA256())
        .build(password.encode("ascii"))
    )
    return pkcs12.serialize_key_and_certificates(b"client", key, leaf, certificates[1:], encryption)


def ca_truststore(pem_bundle: bytes) -> bytes:
    """Export unique CA certificates as Java trustedCertEntry values."""
    unique = {cert.fingerprint(hashes.SHA256()): cert for cert in _certificates(pem_bundle) if _is_ca(cert)}
    if not unique:
        raise ValueError("Trust bundle contains no CA certificates")
    entries = [
        pkcs12.PKCS12Certificate(cert, f"cert-{fingerprint.hex()}".encode("ascii"))
        for fingerprint, cert in unique.items()
    ]
    # This compatibility format holds public certificates only.
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(50_000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1())  # nosec B303
        .build(TRUSTSTORE_PASSWORD.encode("ascii"))
    )
    return pkcs12.serialize_java_truststore(entries, encryption)
