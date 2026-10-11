"""Internal authority boundary. This is not a proposed Core wire format."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
import base64
import hashlib
import json
import re
from typing import Literal, Protocol
from uuid import UUID

from starlette.requests import Request

from opendefence_integration_tak.certificates import (
    ClientCredential,
    PublicCredential,
    public_credential,
    validate_ca_bundle,
    validate_client_credential,
)
from opendefence_integration_tak.packages import PackageSettings, validate_settings


class DeliveryError(Exception):
    """Public error codes contain no request, certificate or storage contents."""

    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code
        super().__init__(code)


def compact_uuid(value: UUID) -> str:
    return base64.urlsafe_b64encode(value.bytes).decode().rstrip("=")


def parse_user_id(value: str) -> UUID:
    if re.fullmatch(r"[A-Za-z0-9_-]{22}", value):
        result = UUID(bytes=base64.urlsafe_b64decode(value + "=="))
        if compact_uuid(result) == value:
            return result
    elif re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
        return UUID(value)
    raise DeliveryError(404, "not-found")


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    credential_id: str
    valid_until: datetime

    def check_validity(self, now: datetime) -> None:
        if self.valid_until.tzinfo is None or self.valid_until <= now:
            raise DeliveryError(403, "access-denied")


@dataclass(frozen=True, slots=True)
class ApprovedCredential:
    id: str
    record: PublicCredential
    purpose: Literal["main", "tak-client"]
    source: Literal["reused-main", "tak-generated"]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PackageSnapshot:
    """A fresh Core decision plus verified server readback, never a cache assertion.

    The adapter must enforce effective access and high-OPSEC delivery rules for the
    authorizing generation, including when that generation is checked on redemption.
    Rotation data is Core-owned. No observer or download can synthesize confirmation.
    """

    settings: PackageSettings
    approved: tuple[ApprovedCredential, ...]
    selected_id: str | None
    authority_until: datetime
    desired_revision: str
    messaging_revision: str | None
    api_revision: str | None
    material: ClientCredential | None = field(repr=False)
    trust_pem: bytes = field(repr=False)
    rotation: dict[str, object]
    unready_state: Literal["pending", "degraded"] = "pending"

    def state(self, now: datetime) -> str:
        self.check_authority(now)
        if not self.desired_revision or (
            self.desired_revision != self.messaging_revision or self.desired_revision != self.api_revision
        ):
            return self.unready_state
        if self.material is None or self.selected_id is None:
            return self.unready_state
        self.exported(now)
        return "ready"

    def check_authority(self, now: datetime) -> None:
        if self.authority_until.tzinfo is None or self.authority_until <= now:
            raise DeliveryError(503, "authority-unavailable")

    def exported(self, now: datetime) -> ApprovedCredential:
        selected = next((item for item in self.approved if item.id == self.selected_id), None)
        if selected is None or self.material is None:
            raise DeliveryError(503, "package-unavailable")
        try:
            validate_settings(self.settings)
            _, certificates = validate_client_credential(self.material, now=now)
            validate_ca_bundle(self.trust_pem)
            if self.material.expected_user_id != self.settings.user_id:
                raise ValueError("Credential identity mismatch")
            record = public_credential(certificates)
        except ValueError, DeliveryError:
            raise DeliveryError(503, "package-unavailable") from None
        if (
            selected.expires_at.tzinfo is None
            or selected.expires_at <= now
            or selected.record != record
            or selected.expires_at > record.not_after
            or len({item.id for item in self.approved}) != len(self.approved)
        ):
            raise DeliveryError(503, "package-unavailable")
        return selected

    def revision(self, profile_id: str) -> str:
        """Bind immutable delivery inputs; callsign and server status are separate."""
        value = [
            profile_id,
            "full-v1",
            self.settings.deployment_id,
            str(self.settings.user_id),
            self.settings.host,
            self.settings.port,
            self.selected_id,
            hashlib.sha256(self.material.certificate_chain_pem if self.material else b"").hexdigest(),
            hashlib.sha256(
                self.material.private_key_pem + self.material.password.encode() if self.material else b""
            ).hexdigest(),
            hashlib.sha256(self.trust_pem).hexdigest(),
        ]
        return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


class Authority(Protocol):
    async def authenticate(self, request: Request) -> Principal:
        """Validate exact current mTLS credential through the trusted Core boundary."""
        ...

    async def authorize(self, user_id: UUID, credential_id: str, now: datetime) -> Principal:
        """Recheck a previously authenticated generation, without requiring a browser certificate."""
        ...

    async def package(self, principal: Principal, profile_id: str, now: datetime) -> PackageSnapshot:
        """Read current entitlement, inventory, material, deadlines and strict server readback."""
        ...


class UnavailableAuthority:
    """Default until the Core identity/inventory/delivery semantics are supplied."""

    async def authenticate(self, request: Request) -> Principal:
        raise DeliveryError(503, "authority-unavailable")

    async def authorize(self, user_id: UUID, credential_id: str, now: datetime) -> Principal:
        raise DeliveryError(503, "authority-unavailable")

    async def package(self, principal: Principal, profile_id: str, now: datetime) -> PackageSnapshot:
        raise DeliveryError(503, "authority-unavailable")


def utc_now() -> datetime:
    return datetime.now(UTC)
