"""Bounded PKCS#12 export of existing credentials and public trust anchors."""

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12

MAX_PEM_BYTES = 1024 * 1024
MAX_CERTIFICATES = 32
MAX_KEY_BYTES = 16 * 1024
ACCEPTED_CREDENTIALS_ANNOTATION = "platform.opendefence.fi/accepted-credentials"
# This password protects public certificates only.
TRUSTSTORE_PASSWORD = "public"  # nosec B105  # pragma: allowlist secret


@dataclass(frozen=True, slots=True)
class ClientCredential:
    """Already-issued material; the authoritative adapter supplies the User UUID."""

    certificate_chain_pem: bytes = field(repr=False)
    private_key_pem: bytes = field(repr=False)
    password: str = field(repr=False)
    expected_user_id: UUID


@dataclass(frozen=True, slots=True)
class PublicCredential:
    """Public leaf metadata supplied by Core and checked against export material."""

    fingerprint_sha256: str
    serial_hex: str
    issuer_id: str
    not_before: datetime
    not_after: datetime


def accepted_credential_records(raw: str | None, *, now: datetime) -> tuple[PublicCredential, ...]:
    """Read Core's provisional complete accepted set. Invalid metadata grants no access."""
    if now.utcoffset() is None or not raw or len(raw) > 64_000:
        raise ValueError("Accepted credential metadata is unavailable")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Accepted credential metadata has duplicate keys")
        return result

    try:
        payload: object = json.loads(raw, object_pairs_hook=unique_object)
    except json.JSONDecodeError:
        raise ValueError("Accepted credential metadata is malformed") from None
    if (
        not isinstance(payload, dict)
        or set(payload) != {"version", "credentials"}
        or type(payload["version"]) is not int
        or payload["version"] != 1
    ):
        raise ValueError("Accepted credential metadata has an unsupported version")
    items = payload["credentials"]
    if not isinstance(items, list) or not 0 < len(items) <= 32:
        raise ValueError("Accepted credential set is empty or too large")
    records: list[PublicCredential] = []
    identities: set[tuple[str, str]] = set()
    fingerprints: set[str] = set()
    for item in items:
        fields = {"fingerprintSha256", "serialHex", "issuerId", "notBefore", "notAfter"}
        if not isinstance(item, dict) or set(item) != fields or any(not isinstance(item[key], str) for key in fields):
            raise ValueError("Accepted credential record is malformed")
        fingerprint, serial, issuer = item["fingerprintSha256"], item["serialHex"], item["issuerId"]
        if (
            re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or re.fullmatch(r"[1-9a-f][0-9a-f]{0,39}", serial) is None
            or re.fullmatch(r"issuer-sha256:[0-9a-f]{64}", issuer) is None
        ):
            raise ValueError("Accepted credential record has an invalid identifier")
        try:
            not_before = datetime.fromisoformat(item["notBefore"].replace("Z", "+00:00"))
            not_after = datetime.fromisoformat(item["notAfter"].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Accepted credential validity is malformed") from None
        if not_before.utcoffset() is None or not_after.utcoffset() is None or not_before >= not_after:
            raise ValueError("Accepted credential validity is malformed")
        if fingerprint in fingerprints or (issuer, serial) in identities:
            raise ValueError("Accepted credential record is duplicated")
        fingerprints.add(fingerprint)
        identities.add((issuer, serial))
        if not_before <= now < not_after:
            records.append(PublicCredential(fingerprint, serial, issuer, not_before, not_after))
    if not records:
        raise ValueError("No accepted credential is currently valid")
    return tuple(sorted(records, key=lambda record: record.fingerprint_sha256))


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


def validate_client_credential(
    credential: ClientCredential, *, now: datetime
) -> tuple[rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey, list[x509.Certificate]]:
    """Check export inputs without PKCS#12 encryption; return parsed key and chain."""
    if now.utcoffset() is None:
        raise ValueError("An aware verification time is required")
    password = credential.password
    if not 6 <= len(password) <= 128 or not password.isascii() or not password.isprintable():
        raise ValueError("PKCS#12 password must be 6 to 128 printable ASCII characters")
    certificates = _certificates(credential.certificate_chain_pem)
    leaf = certificates[0]
    if _is_ca(leaf) or not leaf.not_valid_before_utc <= now < leaf.not_valid_after_utc:
        raise ValueError("Client certificate is not a currently valid leaf")
    if not isinstance(credential.expected_user_id, UUID):
        raise ValueError("Expected User ID must be a UUID")
    names: list[str]
    try:
        names = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
            x509.UniformResourceIdentifier
        )
    except x509.ExtensionNotFound:
        names = []
    if [name for name in names if name.lower().startswith("urn:uuid:")] != [f"urn:uuid:{credential.expected_user_id}"]:
        raise ValueError("Client certificate does not match the expected User URI SAN")
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
    return key, certificates


def public_credential(certificates: list[x509.Certificate]) -> PublicCredential:
    """Derive the public record from a leaf and its issuing CA certificate."""
    if len(certificates) < 2 or not _is_ca(certificates[1]):
        raise ValueError("Client chain needs its issuing CA certificate")
    leaf, issuer = certificates[:2]
    leaf.verify_directly_issued_by(issuer)
    issuer_key = issuer.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return PublicCredential(
        leaf.fingerprint(hashes.SHA256()).hex(),
        format(leaf.serial_number, "x"),
        "issuer-sha256:" + hashlib.sha256(issuer.subject.public_bytes() + issuer_key).hexdigest(),
        leaf.not_valid_before_utc,
        leaf.not_valid_after_utc,
    )


def client_keystore(credential: ClientCredential, *, now: datetime) -> bytes:
    """Export one key and its leaf-first chain. Do not issue or approve credentials."""
    key, certificates = validate_client_credential(credential, now=now)
    # The public truststore's legacy encryption must never protect the client key.
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(600_000)
        .key_cert_algorithm(pkcs12.PBES.PBESv2SHA256AndAES256CBC)
        .hmac_hash(hashes.SHA256())
        .build(credential.password.encode("ascii"))
    )
    return pkcs12.serialize_key_and_certificates(b"client", key, certificates[0], certificates[1:], encryption)


def validate_ca_bundle(pem_bundle: bytes) -> dict[bytes, x509.Certificate]:
    """Check a bounded CA bundle without producing a truststore."""
    unique = {cert.fingerprint(hashes.SHA256()): cert for cert in _certificates(pem_bundle) if _is_ca(cert)}
    if not unique:
        raise ValueError("Trust bundle contains no CA certificates")
    return unique


def ca_truststore(pem_bundle: bytes) -> bytes:
    """Export unique CA certificates as Java trustedCertEntry values."""
    unique = validate_ca_bundle(pem_bundle)
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
