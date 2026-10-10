"""Verify package formats, stable credential paths, and XML/path boundaries."""

from dataclasses import replace
import base64
from typing import cast
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID
from xml.etree import ElementTree as ET  # nosec B405 - Parses only XML generated from test fixtures.
from zipfile import ZipFile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
import pytest

from opendefence_integration_tak.packages import PROFILE_IDS, PackageSettings, build_package
from tests.conftest import CredentialFixture

SETTINGS = PackageSettings("alpha", UUID("00000000-0000-4000-8000-000000000001"), "tak.example.test", 'Fox & <"ä">')


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_profile_archive_and_preference_contract(material: CredentialFixture, profile: str) -> None:
    package = build_package(profile, SETTINGS, material.credential, material.trust_pem, now=material.now)
    assert package.file_name.endswith(".zip")
    assert "content=" not in repr(package)
    with ZipFile(BytesIO(package.content)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == 4
        assert all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts for name in names)
        manifest = ET.fromstring(archive.read("MANIFEST/manifest.xml"))  # nosec B314 - Fixture-generated XML.
        contents = [entry.attrib["zipEntry"] for entry in manifest.findall("Contents/Content")]
        assert contents == names[1:]
        assert all(name.endswith(".p12") for name in contents[:2]) and contents[2] == "server.pref"
        parameters = {
            entry.attrib["name"]: entry.attrib["value"] for entry in manifest.findall("Configuration/Parameter")
        }
        assert ("onReceiveImport" in parameters) == (profile != "itak")
        preferences = ET.fromstring(archive.read("server.pref"))  # nosec B314 - Fixture-generated XML.
        blocks = {block.attrib["name"]: {entry.attrib["key"]: entry.text for entry in block} for block in preferences}
        streams = blocks["cot_streams"]
        assert streams["connectString0"] == "tak.example.test:8089:ssl"
        app = blocks["gov.tak.taktracker_preferences" if profile == "tak-tracker" else "com.atakmap.app_preferences"]
        if profile == "tak-tracker":
            assert app == {"callsign": SETTINGS.callsign}
        elif profile == "itak":
            assert "locationCallsign" not in app
        else:
            assert app["locationCallsign"] == SETTINGS.callsign
        for key, filename in (("caLocation", contents[0]), ("certificateLocation", contents[1])):
            if profile != "tak-tracker":
                assert app[key] == f"cert/{filename}"
            if profile in ("atak", "atak-mini", "tak-tracker"):
                assert streams[f"{key}0"] == f"cert/{filename}"
            else:
                assert f"{key}0" not in streams
        assert b"disablePreferenceItem_locationCallsign" not in archive.read("server.pref")
        client = pkcs12.load_pkcs12(archive.read(contents[1]), material.credential.password.encode())
        assert client.key is not None and client.cert is not None and client.cert.certificate == material.leaf
        assert len([name for name in names if name.endswith("-client.p12")]) == 1
        assert pkcs12.load_pkcs12(archive.read(contents[0]), b"public").key is None


def test_rotation_and_callsign_keep_internal_paths(material: CredentialFixture) -> None:
    original = build_package("atak", SETTINGS, material.credential, material.trust_pem, now=material.now)
    key = ec.generate_private_key(ec.SECP256R1())
    successor = (
        x509.CertificateBuilder()
        .subject_name(material.leaf.subject)
        .issuer_name(material.leaf.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(material.leaf.not_valid_before_utc)
        .not_valid_after(material.leaf.not_valid_after_utc)
        .sign(key, hashes.SHA256())
    )
    credential = replace(
        material.credential,
        certificate_chain_pem=successor.public_bytes(serialization.Encoding.PEM),
        private_key_pem=key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
    )
    updated = build_package(
        "atak", replace(SETTINGS, callsign="CHANGED"), credential, material.trust_pem, now=material.now
    )
    assert updated.file_name != original.file_name
    with ZipFile(BytesIO(original.content)) as first, ZipFile(BytesIO(updated.content)) as second:
        assert first.namelist() == second.namelist()
        client_name = next(name for name in first.namelist() if name.endswith("-client.p12"))
        loaded = pkcs12.load_pkcs12(second.read(client_name), credential.password.encode())
        assert loaded.cert is not None and loaded.cert.certificate == successor
        assert b"CHANGED" in second.read("server.pref")
        assert "CHANGED" not in client_name
    for settings, profile in (
        (replace(SETTINGS, deployment_id="bravo"), "atak"),
        (SETTINGS, "wintak"),
    ):
        other = build_package(profile, settings, material.credential, material.trust_pem, now=material.now)
        with ZipFile(BytesIO(original.content)) as first, ZipFile(BytesIO(other.content)) as second:
            assert not {name for name in first.namelist() if name.endswith(".p12")} & {
                name for name in second.namelist() if name.endswith(".p12")
            }


@pytest.mark.parametrize("deployment", ["", "../escape", "a/b", "Alpha", "a_underscore", "a" * 64, "-alpha", "alpha-"])
def test_reject_unsafe_deployment(material: CredentialFixture, deployment: str) -> None:
    with pytest.raises(ValueError, match="Deployment ID"):
        build_package(
            "atak",
            replace(SETTINGS, deployment_id=deployment),
            material.credential,
            material.trust_pem,
            now=material.now,
        )


@pytest.mark.parametrize(
    "host", ["", "https://tak.example", "tak:8089:tcp", "[::1]", "::1", "a..b", "a" * 254, "bad_name"]
)
def test_reject_unsafe_connection(material: CredentialFixture, host: str) -> None:
    with pytest.raises(ValueError):
        build_package("atak", replace(SETTINGS, host=host), material.credential, material.trust_pem, now=material.now)


@pytest.mark.parametrize("port", [0, 65536, True])
def test_reject_bad_port(material: CredentialFixture, port: int) -> None:
    with pytest.raises(ValueError, match="Port"):
        build_package("atak", replace(SETTINGS, port=port), material.credential, material.trust_pem, now=material.now)


@pytest.mark.parametrize("callsign", ["", "a" * 129, "control\x00", "control\n", "surrogate\ud800", "invalid\uffff"])
def test_reject_invalid_xml(material: CredentialFixture, callsign: str) -> None:
    with pytest.raises(ValueError, match="Callsign"):
        build_package(
            "atak", replace(SETTINGS, callsign=callsign), material.credential, material.trust_pem, now=material.now
        )


def test_reject_unknown_profile(material: CredentialFixture) -> None:
    with pytest.raises(ValueError, match="Unknown package profile"):
        build_package("../unknown", SETTINGS, material.credential, material.trust_pem, now=material.now)


def test_ipv4_connection(material: CredentialFixture) -> None:
    package = build_package(
        "atak",
        replace(SETTINGS, host="192.0.2.1", port=8443),
        material.credential,
        material.trust_pem,
        now=material.now,
    )
    with ZipFile(BytesIO(package.content)) as archive:
        assert b"192.0.2.1:8443:ssl" in archive.read("server.pref")


@pytest.mark.parametrize("cn", ["not-a-uuid", "A" * 21, "A" * 21 + "B"])
def test_reject_bad_identity_encoding(material: CredentialFixture, cn: str) -> None:
    with pytest.raises(ValueError, match="CN"):
        build_package(
            "atak", SETTINGS, replace(material.credential, expected_cn=cn), material.trust_pem, now=material.now
        )


def test_compact_cn_and_user_isolation(material: CredentialFixture) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    cn = base64.urlsafe_b64encode(SETTINGS.user_id.bytes).decode().rstrip("=")
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, cn)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(material.leaf.not_valid_before_utc)
        .not_valid_after(material.leaf.not_valid_after_utc)
        .sign(key, hashes.SHA256())
    )
    credential = replace(
        material.credential,
        expected_cn=cn,
        certificate_chain_pem=certificate.public_bytes(serialization.Encoding.PEM),
        private_key_pem=key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
    )
    canonical = build_package("atak", SETTINGS, material.credential, material.trust_pem, now=material.now)
    compact = build_package("atak", SETTINGS, credential, material.trust_pem, now=material.now)
    with ZipFile(BytesIO(canonical.content)) as first, ZipFile(BytesIO(compact.content)) as second:
        assert first.namelist() == second.namelist()
    with pytest.raises(ValueError, match="different User UUID"):
        build_package(
            "atak", replace(SETTINGS, user_id=UUID(int=2)), material.credential, material.trust_pem, now=material.now
        )


def test_reject_unparsed_user_id(material: CredentialFixture) -> None:
    with pytest.raises(ValueError, match="User ID must be a UUID"):
        build_package(
            "atak",
            replace(SETTINGS, user_id=cast(UUID, "unparsed")),
            material.credential,
            material.trust_pem,
            now=material.now,
        )
