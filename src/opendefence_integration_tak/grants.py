"""Bounded, compare-and-swap Secret storage shared by API replicas."""

import base64
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from cloudcoil.client import AsyncAPIClient
from cloudcoil.errors import APIError, ResourceConflict
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from opendefence_integration_tak.delivery import DeliveryError
from opendefence_integration_tak.resources import Secret

MAX_GRANTS = 256
MAX_USER_GRANTS = 8
_MAX_SECRET_BYTES = 600_000


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{22}$")
    user_id: UUID
    profile_id: str
    credential_id: str
    authorizing_id: str
    token_hash: str = Field(pattern=r"^[0-9a-f]{64}$", repr=False)
    created_at: datetime
    expires_at: datetime
    target_revision: str


class GrantDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    store_uid: str
    grants: dict[str, Grant] = Field(default_factory=dict, max_length=MAX_GRANTS)


class GrantStore(Protocol):
    async def get(self, grant_id: str) -> Grant | None: ...
    async def create(self, grant: Grant, now: datetime) -> None: ...
    async def delete(self, grant_id: str, user_id: UUID) -> None: ...


class SecretGrantStore:
    """One small CAS document avoids per-grant locks and cross-object transactions.

    A restored Secret has a new Kubernetes UID, so grants from its previous
    incarnation are ignored. Pod restarts and multiple API replicas share grants.
    """

    def __init__(self, client: AsyncAPIClient[Secret], name: str = "tak-download-grants") -> None:
        self.client = client
        self.name = name

    async def _read(self) -> tuple[Secret, GrantDocument]:
        secret = await self.client.get(self.name)
        if secret.metadata is None or not secret.metadata.uid or not secret.metadata.resource_version:
            raise DeliveryError(503, "grant-store-unavailable")
        uid = secret.metadata.uid
        encoded = secret.data.get("grants.json")
        if encoded is None:
            return secret, GrantDocument(store_uid=uid)
        if len(encoded) > _MAX_SECRET_BYTES * 4 // 3:
            raise DeliveryError(503, "grant-store-unavailable")
        raw = base64.b64decode(encoded, validate=True)
        document = GrantDocument.model_validate_json(raw)
        if document.store_uid != uid:
            document = GrantDocument(store_uid=uid)
        if any(
            key != grant.id or grant.expires_at.tzinfo is None or grant.created_at.tzinfo is None
            for key, grant in document.grants.items()
        ):
            raise DeliveryError(503, "grant-store-unavailable")
        return secret, document

    async def get(self, grant_id: str) -> Grant | None:
        try:
            _, document = await self._read()
            return document.grants.get(grant_id)
        except APIError, httpx.RequestError, ValidationError, ValueError:
            raise DeliveryError(503, "grant-store-unavailable") from None

    async def _write(self, secret: Secret, document: GrantDocument) -> None:
        raw = document.model_dump_json().encode()
        if len(raw) > _MAX_SECRET_BYTES:
            raise DeliveryError(429, "grant-limit")
        secret.data["grants.json"] = base64.b64encode(raw).decode()
        await self.client.update(secret)

    async def create(self, grant: Grant, now: datetime) -> None:
        try:
            for _ in range(4):
                secret, document = await self._read()
                document.grants = {key: item for key, item in document.grants.items() if item.expires_at > now}
                if grant.id in document.grants:
                    raise DeliveryError(503, "grant-store-unavailable")
                if (
                    len(document.grants) >= MAX_GRANTS
                    or sum(item.user_id == grant.user_id for item in document.grants.values()) >= MAX_USER_GRANTS
                ):
                    raise DeliveryError(429, "grant-limit")
                document.grants[grant.id] = grant
                try:
                    await self._write(secret, document)
                    return
                except ResourceConflict:
                    continue
        except APIError, httpx.RequestError, ValidationError, ValueError:
            raise DeliveryError(503, "grant-store-unavailable") from None
        raise DeliveryError(503, "grant-store-unavailable")

    async def delete(self, grant_id: str, user_id: UUID) -> None:
        try:
            for _ in range(4):
                secret, document = await self._read()
                grant = document.grants.get(grant_id)
                if grant is None:
                    return
                if grant.user_id != user_id:
                    raise DeliveryError(404, "not-found")
                del document.grants[grant_id]
                try:
                    await self._write(secret, document)
                    return
                except ResourceConflict:
                    continue
        except APIError, httpx.RequestError, ValidationError, ValueError:
            raise DeliveryError(503, "grant-store-unavailable") from None
        raise DeliveryError(503, "grant-store-unavailable")
