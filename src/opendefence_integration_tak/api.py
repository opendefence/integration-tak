"""Seven resource-oriented routes; no JVM or credential issuance."""

from collections.abc import Callable
import asyncio
from datetime import datetime, timedelta
import hashlib
import hmac
from http import HTTPStatus
import json
import logging
import re
import secrets
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from opendefence_integration_tak.delivery import (
    Authority,
    DeliveryError,
    PackageSnapshot,
    Principal,
    compact_uuid,
    parse_user_id,
    utc_now,
)
from opendefence_integration_tak.grants import Grant, GrantStore
from opendefence_integration_tak.packages import PROFILE_IDS, build_package

PREFIX = "/integrations/tak/api/v1"
_PRIVATE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}
_GRANT_ID = re.compile(r"[A-Za-z0-9_-]{22}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.zip")
_LOGGER = logging.getLogger(__name__)


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expiresInSeconds: int = Field(default=300, ge=1, le=300)
    variant: str = "full"
    baseRevision: str | None = Field(default=None, min_length=1, max_length=160)
    compatibilityId: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_variant(self) -> "GrantRequest":
        if self.variant not in ("full", "credential-update"):
            raise ValueError("Invalid variant")
        if self.variant == "full":
            if {"baseRevision", "compatibilityId"} & self.model_fields_set:
                raise ValueError("Full packages have no update selectors")
        elif self.baseRevision is None or self.compatibilityId is None:
            raise ValueError("Update selectors are required")
        return self


def _json(value: object, status: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(value, status_code=status, headers=_PRIVATE_HEADERS | (headers or {}))


def _metadata(value: object, request: Request) -> Response:
    etag = '"' + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest() + '"'
    matches = [item.strip().removeprefix("W/") for item in request.headers.get("if-none-match", "").split(",")]
    if etag in matches or "*" in matches:
        return Response(status_code=304, headers=_PRIVATE_HEADERS | {"ETag": etag})
    return _json(value, headers={"ETag": etag})


def _grant_metadata(grant: Grant, now: datetime) -> dict[str, object]:
    return {
        "id": grant.id,
        "userId": compact_uuid(grant.user_id),
        "profileId": grant.profile_id,
        "credentialId": grant.credential_id,
        "createdAt": grant.created_at.isoformat(),
        "expiresAt": grant.expires_at.isoformat(),
        "state": "active" if grant.expires_at > now else "expired",
        "reusableUntilExpiry": True,
        "links": {"self": f"{PREFIX}/download-grants/{grant.id}"},
        "variant": "full",
        "targetRevision": grant.target_revision,
    }


def _profile(request: Request) -> str:
    value = request.path_params["profile_id"]
    if value not in PROFILE_IDS:
        raise DeliveryError(404, "not-found")
    return value


def _selectors(request: Request) -> GrantRequest:
    if any(
        key not in ("variant", "baseRevision", "compatibilityId") or len(request.query_params.getlist(key)) != 1
        for key in request.query_params
    ):
        raise DeliveryError(422, "invalid-request")
    try:
        return GrantRequest.model_validate(dict(request.query_params))
    except ValidationError:
        raise DeliveryError(422, "invalid-request") from None


class PackageAPI:
    def __init__(
        self, authority: Authority, grants: GrantStore, public_origin: str, clock: Callable[[], datetime] = utc_now
    ) -> None:
        origin = urlsplit(public_origin)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.username is not None
            or origin.password is not None
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
        ):
            raise ValueError("Public origin must be an HTTPS origin without credentials or a path")
        self.authority = authority
        self.grants = grants
        self.public_origin = public_origin.rstrip("/")
        self.clock = clock
        self.renders = asyncio.Semaphore(4)

    def check_origin(self, request: Request) -> None:
        origins = request.headers.getlist("origin")
        if (origins and origins != [self.public_origin]) or request.headers.get("sec-fetch-site") == "cross-site":
            raise DeliveryError(403, "origin-denied")

    async def principal(self, request: Request) -> Principal:
        principal = await self.authority.authenticate(request)
        return await self.current_principal(principal)

    async def current_principal(self, principal: Principal) -> Principal:
        current = await self.authority.authorize(principal.user_id, principal.credential_id, self.clock())
        if current.user_id != principal.user_id or current.credential_id != principal.credential_id:
            raise DeliveryError(403, "access-denied")
        current.check_validity(self.clock())
        return current

    async def snapshot(self, principal: Principal, profile_id: str) -> PackageSnapshot:
        snapshot = await self.authority.package(principal, profile_id, self.clock())
        if snapshot.settings.user_id != principal.user_id:
            raise DeliveryError(503, "authority-unavailable")
        snapshot.check_authority(self.clock())
        return snapshot

    async def self_package(self, request: Request) -> tuple[Principal, str, PackageSnapshot]:
        principal = await self.principal(request)
        if parse_user_id(request.path_params["user_id"]) != principal.user_id:
            raise DeliveryError(403, "access-denied")
        profile_id = _profile(request)
        return principal, profile_id, await self.snapshot(principal, profile_id)

    async def profiles(self, request: Request) -> Response:
        await self.principal(request)
        titles = ("ATAK", "ATAK Mini", "iTAK", "WinTAK", "TAK Tracker")
        empty: list[str] = []
        value = {
            "items": [
                {
                    "id": profile,
                    "title": title,
                    "version": "1",
                    "validationStatus": "implemented",
                    "validatedClients": empty,
                    "rotationCompatibility": {"status": "unverified", "methods": empty},
                }
                for profile, title in zip(PROFILE_IDS, titles, strict=True)
            ]
        }
        return _metadata(value, request)

    async def package_metadata(self, request: Request) -> Response:
        _, profile, snapshot = await self.self_package(request)
        state = snapshot.state(self.clock())
        base = f"{PREFIX}/users/{compact_uuid(snapshot.settings.user_id)}/client-packages/{profile}"
        value: dict[str, object] = {
            "userId": compact_uuid(snapshot.settings.user_id),
            "profileId": profile,
            "state": state,
            "callsign": snapshot.settings.callsign,
            "revision": snapshot.revision(profile),
            "links": {"content": base + "/content", "downloadGrants": base + "/download-grants"},
            "takAuthorization": {
                "state": "ready"
                if snapshot.desired_revision
                and snapshot.desired_revision == snapshot.messaging_revision == snapshot.api_revision
                else snapshot.unready_state,
                "revision": snapshot.desired_revision,
                "credentialIds": [item.id for item in snapshot.approved],
            },
            "credentialUpdate": {"state": "unsupported", "compatibilityIds": []},
            "rotation": snapshot.rotation,
        }
        if state == "ready":
            credential = snapshot.exported(self.clock())
            value["credential"] = {
                "id": credential.id,
                "purpose": credential.purpose,
                "source": credential.source,
                "expiresAt": credential.expires_at.isoformat(),
            }
        else:
            value["reason"] = "current-projection-or-material-required"
        return _metadata(value, request)

    async def render(self, snapshot: PackageSnapshot, profile: str) -> Response:
        if self.renders.locked():
            raise DeliveryError(429, "render-limit")
        async with self.renders:
            return await run_in_threadpool(self._render, snapshot, profile)

    def _render(self, snapshot: PackageSnapshot, profile: str) -> Response:
        if snapshot.state(self.clock()) != "ready" or snapshot.material is None:
            raise DeliveryError(503, "package-unavailable")
        try:
            package = build_package(profile, snapshot.settings, snapshot.material, snapshot.trust_pem, now=self.clock())
        except ValueError:
            raise DeliveryError(503, "package-unavailable") from None
        return Response(
            package.content,
            media_type="application/zip",
            headers=_PRIVATE_HEADERS
            | {
                "Content-Disposition": f'attachment; filename="{package.file_name}"',
            },
        )

    async def content(self, request: Request) -> Response:
        principal, profile, snapshot = await self.self_package(request)
        selectors = _selectors(request)
        if selectors.variant != "full":
            raise DeliveryError(409, "update-not-supported")
        response = await self.render(snapshot, profile)
        # Rendering is expensive; recheck policy and immutable inputs before releasing bytes.
        principal = await self.current_principal(principal)
        fresh = await self.snapshot(principal, profile)
        if fresh.state(self.clock()) != "ready" or fresh.revision(profile) != snapshot.revision(profile):
            raise DeliveryError(503, "package-unavailable")
        principal.check_validity(self.clock())
        return response

    async def create_grant(self, request: Request) -> Response:
        self.check_origin(request)
        principal, profile, snapshot = await self.self_package(request)
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise DeliveryError(422, "invalid-request")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                raise DeliveryError(422, "invalid-request")
        try:
            selectors = GrantRequest.model_validate_json(body)
        except ValidationError:
            raise DeliveryError(422, "invalid-request") from None
        if selectors.variant != "full":
            raise DeliveryError(409, "update-not-supported")
        now = self.clock()
        if snapshot.state(now) != "ready":
            raise DeliveryError(503, "package-unavailable")
        credential = snapshot.exported(now)
        expires = min(
            now + timedelta(seconds=selectors.expiresInSeconds),
            principal.valid_until,
            snapshot.authority_until,
            credential.expires_at,
        )
        if expires <= now:
            raise DeliveryError(503, "package-unavailable")
        token = secrets.token_urlsafe(32)
        grant = Grant(
            id=secrets.token_urlsafe(16),
            user_id=principal.user_id,
            profile_id=profile,
            credential_id=credential.id,
            authorizing_id=principal.credential_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now,
            expires_at=expires,
            target_revision=snapshot.revision(profile),
        )
        await self.grants.create(grant, now)
        value = _grant_metadata(grant, now)
        value["downloadUrl"] = f"{self.public_origin}{PREFIX}/downloads/{grant.id}/package.zip?token={token}"
        return _json(value, 201, {"Location": f"{PREFIX}/download-grants/{grant.id}"})

    async def grant_metadata(self, request: Request) -> Response:
        principal = await self.principal(request)
        grant_id = request.path_params["grant_id"]
        if _GRANT_ID.fullmatch(grant_id) is None:
            raise DeliveryError(404, "not-found")
        grant = await self.grants.get(grant_id)
        if grant is None or grant.user_id != principal.user_id:
            raise DeliveryError(404, "not-found")
        return _json(_grant_metadata(grant, self.clock()))

    async def delete_grant(self, request: Request) -> Response:
        self.check_origin(request)
        principal = await self.principal(request)
        grant_id = request.path_params["grant_id"]
        if _GRANT_ID.fullmatch(grant_id) is None:
            raise DeliveryError(404, "not-found")
        await self.grants.delete(grant_id, principal.user_id)
        return Response(status_code=204, headers=_PRIVATE_HEADERS)

    async def redeem(self, request: Request) -> Response:
        grant_id, file_name = request.path_params["grant_id"], request.path_params["file_name"]
        tokens = request.query_params.getlist("token")
        if (
            _GRANT_ID.fullmatch(grant_id) is None
            or not 5 <= len(file_name) <= 160
            or _FILE_NAME.fullmatch(file_name) is None
            or len(tokens) != 1
            or _TOKEN.fullmatch(tokens[0]) is None
            or set(request.query_params) != {"token"}
        ):
            raise DeliveryError(404, "not-found")
        grant = await self.grants.get(grant_id)
        if (
            grant is None
            or grant.expires_at <= self.clock()
            or not hmac.compare_digest(grant.token_hash, hashlib.sha256(tokens[0].encode()).hexdigest())
        ):
            raise DeliveryError(404, "not-found")
        try:
            principal = await self.authority.authorize(grant.user_id, grant.authorizing_id, self.clock())
            principal = await self.current_principal(principal)
            if principal.user_id != grant.user_id or principal.credential_id != grant.authorizing_id:
                raise DeliveryError(404, "not-found")
            snapshot = await self.snapshot(principal, grant.profile_id)
            self.check_grant_snapshot(grant, snapshot)
            response = await self.render(snapshot, grant.profile_id)
            principal = await self.current_principal(principal)
            fresh = await self.snapshot(principal, grant.profile_id)
            # This is the final grant read: a completed DELETE blocks later release decisions.
            if await self.grants.get(grant_id) != grant or grant.expires_at <= self.clock():
                raise DeliveryError(404, "not-found")
            self.check_grant_snapshot(grant, fresh)
            principal.check_validity(self.clock())
        except DeliveryError as error:
            if error.status in (401, 403, 404):
                raise DeliveryError(404, "not-found") from None
            raise
        return response

    def check_grant_snapshot(self, grant: Grant, snapshot: PackageSnapshot) -> None:
        if snapshot.selected_id != grant.credential_id or snapshot.revision(grant.profile_id) != grant.target_revision:
            raise DeliveryError(404, "not-found")
        if snapshot.state(self.clock()) != "ready":
            raise DeliveryError(503, "package-unavailable")


async def _problem(request: Request, error: Exception) -> Response:
    if isinstance(error, DeliveryError):
        status, code = error.status, error.code
    elif isinstance(error, HTTPException):
        status, code = error.status_code, "not-found" if error.status_code == 404 else "invalid-request"
    else:
        status, code = 503, "service-unavailable"
    return _json({"type": "about:blank", "title": HTTPStatus(status).phrase, "status": status, "code": code}, status)


async def _safe_response(request: Request, call_next: RequestResponseEndpoint) -> Response:
    try:
        return await call_next(request)
    except Exception as error:
        # Adapter errors can contain private material; omit their values and tracebacks.
        _LOGGER.error("Delivery adapter failed (%s)", type(error).__name__)
        return await _problem(request, DeliveryError(503, "service-unavailable"))


def create_app(
    authority: Authority, grants: GrantStore, public_origin: str, clock: Callable[[], datetime] = utc_now
) -> Starlette:
    api = PackageAPI(authority, grants, public_origin, clock)
    user = PREFIX + "/users/{user_id}/client-packages/{profile_id}"
    app = Starlette(
        routes=[
            Route(PREFIX + "/package-profiles", api.profiles, methods=["GET"]),
            Route(user, api.package_metadata, methods=["GET"]),
            Route(user + "/content", api.content, methods=["GET"]),
            Route(user + "/download-grants", api.create_grant, methods=["POST"]),
            Route(PREFIX + "/download-grants/{grant_id}", api.grant_metadata, methods=["GET"]),
            Route(PREFIX + "/download-grants/{grant_id}", api.delete_grant, methods=["DELETE"]),
            Route(PREFIX + "/downloads/{grant_id}/{file_name}", api.redeem, methods=["GET"]),
        ],
        exception_handlers={DeliveryError: _problem, HTTPException: _problem},
        middleware=[Middleware(BaseHTTPMiddleware, dispatch=_safe_response)],
    )
    app.router.redirect_slashes = False
    return app
