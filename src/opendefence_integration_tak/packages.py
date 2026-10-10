"""Build essential full-setup packages without provisioning or filesystem access."""

from dataclasses import dataclass, field
import base64
from datetime import datetime
from io import BytesIO
import ipaddress
import re
from uuid import UUID, uuid4

# XML is constructed here; no external XML is parsed.
from xml.etree import ElementTree as ET  # nosec B405
from zipfile import ZIP_DEFLATED, ZipFile

from opendefence_integration_tak.certificates import (
    ClientCredential,
    TRUSTSTORE_PASSWORD,
    ca_truststore,
    client_keystore,
)

PROFILE_IDS = ("atak", "atak-mini", "itak", "wintak", "tak-tracker")
_SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


@dataclass(frozen=True, slots=True)
class PackageSettings:
    """Explicit connection inputs, independent of unresolved Core resource schemas."""

    deployment_id: str
    user_id: UUID
    host: str
    callsign: str
    port: int = 8089


@dataclass(frozen=True, slots=True)
class RenderedPackage:
    """A fresh outer filename and sensitive ZIP bytes."""

    file_name: str
    content: bytes = field(repr=False)


def validate_settings(settings: PackageSettings) -> None:
    """Check connection and presentation inputs without constructing an archive."""
    if _SLUG.fullmatch(settings.deployment_id) is None:
        raise ValueError("Deployment ID must be a lowercase DNS label")
    if not isinstance(settings.user_id, UUID):
        raise ValueError("User ID must be a UUID")
    if type(settings.port) is not int or not 1 <= settings.port <= 65535:
        raise ValueError("Port must be an integer from 1 to 65535")
    host = settings.host
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not 0 < len(host) <= 253 or any(_DNS_LABEL.fullmatch(label) is None for label in host.split(".")):
            raise ValueError("Host must be a DNS name or IPv4 address") from None
    else:
        if address.version != 4:
            raise ValueError("IPv6 connection syntax needs client validation")
    if not 0 < len(settings.callsign) <= 128 or any(
        not (0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF)
        for char in settings.callsign
    ):
        raise ValueError("Callsign must contain 1 to 128 valid XML characters without controls")


def _entry(parent: ET.Element, key: str, value: str, java_class: str = "String") -> None:
    ET.SubElement(parent, "entry", key=key, **{"class": f"class java.lang.{java_class}"}).text = value


def _preferences(profile_id: str, settings: PackageSettings, credential: ClientCredential, scope: str) -> bytes:
    root = ET.Element("preferences")
    streams = ET.SubElement(root, "preference", version="1", name="cot_streams")
    _entry(streams, "count", "1", "Integer")
    _entry(streams, "description0", settings.deployment_id)
    _entry(streams, "enabled0", "true", "Boolean")
    _entry(streams, "connectString0", f"{settings.host}:{settings.port}:ssl")
    cert_fields = (
        ("caLocation", f"cert/{scope}-ca.p12"),
        ("caPassword", TRUSTSTORE_PASSWORD),
        ("certificateLocation", f"cert/{scope}-client.p12"),
        ("clientPassword", credential.password),
    )
    if profile_id in ("atak", "atak-mini", "tak-tracker"):
        for key, value in cert_fields:
            _entry(streams, f"{key}0", value)
    preference_name = "gov.tak.taktracker_preferences" if profile_id == "tak-tracker" else "com.atakmap.app_preferences"
    preferences = ET.SubElement(root, "preference", version="1", name=preference_name)
    if profile_id == "tak-tracker":
        _entry(preferences, "callsign", settings.callsign)
    else:
        _entry(preferences, "displayServerConnectionWidget", "true", "Boolean")
        for key, value in cert_fields:
            _entry(preferences, key, value)
        # shortcut: iTAK callsign is manual; add a preference only after client validation.
        if profile_id != "itak":
            _entry(preferences, "locationCallsign", settings.callsign)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_package(
    profile_id: str,
    settings: PackageSettings,
    credential: ClientCredential,
    trust_pem: bytes,
    *,
    now: datetime,
) -> RenderedPackage:
    """Render full setup only. Authorization and approval remain the caller's responsibility."""
    if profile_id not in PROFILE_IDS:
        raise ValueError("Unknown package profile")
    validate_settings(settings)
    # Accept the draft's UUID forms without choosing Core's persistence or CN encoding.
    try:
        credential_id = UUID(credential.expected_cn)
    except ValueError:
        if re.fullmatch(r"[A-Za-z0-9_-]{22}", credential.expected_cn) is None:
            raise ValueError("Expected certificate CN must encode a UUID") from None
        credential_id = UUID(bytes=base64.urlsafe_b64decode(credential.expected_cn + "=="))
        if base64.urlsafe_b64encode(credential_id.bytes).decode("ascii").rstrip("=") != credential.expected_cn:
            raise ValueError("Expected certificate CN has a noncanonical compact encoding")
    if credential_id != settings.user_id:
        raise ValueError("Client credential belongs to a different User UUID")
    scope = f"{settings.deployment_id}_{settings.user_id.hex}_{profile_id}"
    files = {
        f"{scope}-ca.p12": ca_truststore(trust_pem),
        f"{scope}-client.p12": client_keystore(credential, now=now),
        "server.pref": _preferences(profile_id, settings, credential, scope),
    }
    package_id = uuid4()
    manifest = ET.Element("MissionPackageManifest", version="2")
    configuration = ET.SubElement(manifest, "Configuration")
    parameters = {"uid": str(package_id), "name": settings.deployment_id, "onReceiveDelete": "false"}
    if profile_id != "itak":
        parameters["onReceiveImport"] = "true"
    for name, value in parameters.items():
        ET.SubElement(configuration, "Parameter", name=name, value=value)
    contents = ET.SubElement(manifest, "Contents")
    for name in files:
        ET.SubElement(contents, "Content", ignore="false", zipEntry=name)
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST/manifest.xml", ET.tostring(manifest, encoding="utf-8", xml_declaration=True))
        for name, data in files.items():
            archive.writestr(name, data)
    return RenderedPackage(f"{scope}-{package_id.hex}.zip", buffer.getvalue())
