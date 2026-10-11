"""Check credential integrity, trust entry semantics, and actual Java imports."""

from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess  # nosec B404 - Runs keytool for fixture compatibility checks.
from typing import TypedDict, cast
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import pkcs12
import pytest

from opendefence_integration_tak.certificates import (
    MAX_CERTIFICATES,
    MAX_KEY_BYTES,
    MAX_PEM_BYTES,
    accepted_credential_records,
    ca_truststore,
    client_keystore,
    public_credential,
    public_credential_records,
)
from tests.conftest import CredentialFixture


class CredentialChanges(TypedDict, total=False):
    expected_user_id: UUID
    password: str
    private_key_pem: bytes
    certificate_chain_pem: bytes


def test_pkcs12_preserves_key_leaf_chain_and_unique_trust(material: CredentialFixture) -> None:
    client = client_keystore(material.credential, now=material.now)
    loaded = pkcs12.load_pkcs12(client, material.credential.password.encode())
    assert loaded.key is not None and loaded.cert is not None
    assert loaded.cert.certificate == material.leaf
    assert loaded.cert.friendly_name == b"client"
    assert [item.certificate for item in loaded.additional_certs] == [material.intermediate, material.root]
    assert loaded.key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ) == material.leaf.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with pytest.raises(ValueError):
        pkcs12.load_pkcs12(client, b"wrong-password")
    public = ca_truststore(material.trust_pem * 2 + material.leaf.public_bytes(serialization.Encoding.PEM))
    trust = pkcs12.load_pkcs12(public, b"public")
    assert trust.key is None and trust.cert is None
    assert {entry.certificate for entry in trust.additional_certs} == {material.root, material.intermediate}
    assert {entry.friendly_name for entry in trust.additional_certs} == {
        f"cert-{cert.fingerprint(hashes.SHA256()).hex()}".encode() for cert in (material.root, material.intermediate)
    }
    assert "fixture-only-password" not in repr(material.credential)
    assert "PRIVATE KEY" not in repr(material.credential)


def test_public_record_uses_leaf_and_issuing_key(material: CredentialFixture) -> None:
    record = public_credential([material.leaf, material.intermediate, material.root])
    issuer_key = material.intermediate.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    assert record.fingerprint_sha256 == material.leaf.fingerprint(hashes.SHA256()).hex()
    assert record.serial_hex == format(material.leaf.serial_number, "x")
    assert (
        record.issuer_id
        == "issuer-sha256:" + hashlib.sha256(material.intermediate.subject.public_bytes() + issuer_key).hexdigest()
    )
    assert (record.not_before, record.not_after) == (
        material.leaf.not_valid_before_utc,
        material.leaf.not_valid_after_utc,
    )
    with pytest.raises(ValueError, match="issuing CA"):
        public_credential([material.leaf])
    with pytest.raises(ValueError):
        public_credential([material.leaf, material.root])


def test_core_public_record_metadata_is_complete_and_current(material: CredentialFixture) -> None:
    record = public_credential([material.leaf, material.intermediate])
    item = {
        "fingerprintSha256": record.fingerprint_sha256,
        "serialHex": record.serial_hex,
        "issuerId": record.issuer_id,
        "notBefore": record.not_before.isoformat(),
        "notAfter": record.not_after.isoformat(),
    }
    payload = {"version": 1, "credentials": [item]}
    assert accepted_credential_records(json.dumps(payload), now=material.now) == (record,)
    replacement = item | {"fingerprintSha256": "c" * 64, "serialHex": "2"}
    overlapping = accepted_credential_records(
        json.dumps({"version": 1, "credentials": [item, replacement]}), now=material.now
    )
    assert {entry.serial_hex for entry in overlapping} == {"2", record.serial_hex}
    expired = item | {"notAfter": material.now.isoformat()}
    successor = next(entry for entry in overlapping if entry.serial_hex == "2")
    assert public_credential_records(json.dumps({"version": 1, "credentials": [expired]}))[0].not_after == material.now
    assert public_credential_records('{"version":1,"credentials":[]}') == ()
    assert accepted_credential_records(
        json.dumps({"version": 1, "credentials": [expired, replacement]}), now=material.now
    ) == (successor,)
    for bad in (
        {"version": 1, "credentials": [item, item]},
        {"version": 1, "credentials": [item | {"issuerId": "untrusted"}]},
        {"version": 1, "credentials": [item | {"serialHex": "00"}]},
        {"version": 1, "credentials": [item | {"notAfter": material.now.isoformat()}]},
    ):
        with pytest.raises(ValueError):
            accepted_credential_records(json.dumps(bad), now=material.now)
    with pytest.raises(ValueError, match="duplicate keys"):
        accepted_credential_records('{"version":1,"version":1,"credentials":[]}', now=material.now)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"expected_user_id": UUID(int=2)}, "User URI SAN"),
        ({"expected_user_id": cast(UUID, "invalid")}, "User ID"),
        ({"password": "short"}, "password"),  # nosec B105 - Invalid test input. # pragma: allowlist secret
        ({"password": "nonascii-ä"}, "password"),  # nosec B105 - Invalid test input. # pragma: allowlist secret
        ({"password": "control\x00character"}, "password"),  # nosec B105 - Invalid test input. # pragma: allowlist secret
        ({"password": "x" * 129}, "password"),
        ({"private_key_pem": b""}, "Private key"),
        ({"private_key_pem": b"x" * (MAX_KEY_BYTES + 1)}, "Private key"),
        ({"certificate_chain_pem": b""}, "Certificate bundle"),
        ({"certificate_chain_pem": b"x" * (MAX_PEM_BYTES + 1)}, "Certificate bundle"),
    ],
)
def test_reject_invalid_export_inputs(material: CredentialFixture, change: CredentialChanges, message: str) -> None:
    credential = replace(
        material.credential,
        expected_user_id=change.get("expected_user_id", material.credential.expected_user_id),
        password=change.get("password", material.credential.password),
        private_key_pem=change.get("private_key_pem", material.credential.private_key_pem),
        certificate_chain_pem=change.get("certificate_chain_pem", material.credential.certificate_chain_pem),
    )
    with pytest.raises(ValueError, match=message):
        client_keystore(credential, now=material.now)


def test_reject_wrong_key_chain_and_validity(material: CredentialFixture) -> None:
    wrong_key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(ValueError, match="does not match"):
        client_keystore(replace(material.credential, private_key_pem=wrong_key), now=material.now)
    unsupported = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(ValueError, match="RSA or EC"):
        client_keystore(replace(material.credential, private_key_pem=unsupported), now=material.now)
    leaf_pem = material.leaf.public_bytes(serialization.Encoding.PEM)
    with pytest.raises(ValueError, match="non-CA"):
        client_keystore(replace(material.credential, certificate_chain_pem=leaf_pem * 2), now=material.now)
    with pytest.raises(ValueError):
        client_keystore(
            replace(
                material.credential,
                certificate_chain_pem=leaf_pem + material.root.public_bytes(serialization.Encoding.PEM),
            ),
            now=material.now,
        )
    for now in (material.now - timedelta(days=2), material.leaf.not_valid_after_utc):
        with pytest.raises(ValueError, match="currently valid"):
            client_keystore(material.credential, now=now)
    with pytest.raises(ValueError, match="aware"):
        client_keystore(material.credential, now=material.now.replace(tzinfo=None))
    with pytest.raises(ValueError, match="valid leaf"):
        client_keystore(
            replace(
                material.credential,
                certificate_chain_pem=material.root.public_bytes(serialization.Encoding.PEM),
                expected_user_id=material.credential.expected_user_id,
            ),
            now=material.now,
        )


@pytest.mark.parametrize("kind", ["empty", "leaf", "missing-constraints", "oversized", "too-many"])
def test_reject_invalid_trust(material: CredentialFixture, kind: str) -> None:
    bundles = {
        "empty": b"",
        "leaf": material.leaf.public_bytes(serialization.Encoding.PEM),
        "oversized": b"x" * (MAX_PEM_BYTES + 1),
        "too-many": material.root.public_bytes(serialization.Encoding.PEM) * (MAX_CERTIFICATES + 1),
    }
    if kind == "missing-constraints":
        key = ec.generate_private_key(ec.SECP256R1())
        cert = (
            x509.CertificateBuilder()
            .subject_name(material.root.subject)
            .issuer_name(material.root.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(material.now)
            .not_valid_after(material.now + timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        bundle = cert.public_bytes(serialization.Encoding.PEM)
    else:
        bundle = bundles[kind]
    with pytest.raises(ValueError):
        ca_truststore(bundle)


def test_java_entry_types_export_and_import(material: CredentialFixture, keytool: str, tmp_path: Path) -> None:
    def run(*arguments: str, password: str) -> str:
        return subprocess.run(  # nosec B603 - Resolved keytool path and fixture arguments; no shell.
            [keytool, "-J-Duser.language=en", *arguments],
            env={**os.environ, "P12_TEST_PASSWORD": password},
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout

    client_path = tmp_path / "client.p12"
    client_path.write_bytes(client_keystore(material.credential, now=material.now))
    trust_path = tmp_path / "trust.p12"
    trust_path.write_bytes(ca_truststore(material.trust_pem))
    for path, password, entry_type, count in (
        (client_path, material.credential.password, "PrivateKeyEntry", 1),
        (trust_path, "public", "trustedCertEntry", 2),
    ):
        listing = run(
            "-list",
            "-v",
            "-storetype",
            "PKCS12",
            "-keystore",
            str(path),
            "-storepass:env",
            "P12_TEST_PASSWORD",
            password=password,
        )
        assert listing.count(f"Entry type: {entry_type}") == count
        assert "Certificate chain length: 3" in listing if path == client_path else "PrivateKeyEntry" not in listing
        destination = tmp_path / f"imported-{path.name}"
        run(
            "-importkeystore",
            "-noprompt",
            "-srckeystore",
            str(path),
            "-srcstoretype",
            "PKCS12",
            "-srcstorepass:env",
            "P12_TEST_PASSWORD",
            "-destkeystore",
            str(destination),
            "-deststoretype",
            "PKCS12",
            "-deststorepass:env",
            "P12_TEST_PASSWORD",
            password=password,
        )
        imported = run(
            "-list", "-v", "-keystore", str(destination), "-storepass:env", "P12_TEST_PASSWORD", password=password
        )
        assert imported.count(f"Entry type: {entry_type}") == count
        expected = [material.leaf] if path == client_path else [material.root, material.intermediate]
        for certificate in expected:
            alias = "client" if path == client_path else f"cert-{certificate.fingerprint(hashes.SHA256()).hex()}"
            exported = tmp_path / "exported.der"
            run(
                "-exportcert",
                "-keystore",
                str(destination),
                "-alias",
                alias,
                "-storepass:env",
                "P12_TEST_PASSWORD",
                "-file",
                str(exported),
                password=password,
            )
            assert x509.load_der_x509_certificate(exported.read_bytes()) == certificate
