"""Exercise delivery with a fixture authority, actual ASGI routes and Secret CAS."""

from collections.abc import Iterator
import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zipfile import ZipFile

from cloudcoil.apimachinery import ObjectMeta
from jsonschema import Draft202012Validator
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from opendefence_integration_tak.api import PREFIX, PackageAPI, create_app
from opendefence_integration_tak.certificates import public_credential
from opendefence_integration_tak.delivery import (
    ApprovedCredential,
    DeliveryError,
    PackageSnapshot,
    Principal,
    UnavailableAuthority,
    compact_uuid,
    parse_user_id,
)
from opendefence_integration_tak.grants import SecretGrantStore
from opendefence_integration_tak.packages import PackageSettings
from opendefence_integration_tak.resources import Secret
from tests.conftest import CredentialFixture
from tests.kubernetes import KubernetesFixture

_SPEC = json.loads((Path(__file__).parents[1] / "docs/package-api.openapi.json").read_text())


def validate_schema(value: object, schema: str) -> None:
    Draft202012Validator({"$ref": f"#/components/schemas/{schema}", "components": _SPEC["components"]}).validate(value)


class FixtureAuthority:
    def __init__(self, material: CredentialFixture) -> None:
        self.now = material.now
        self.principal = Principal(material.credential.expected_user_id, "main-1", material.now + timedelta(hours=1))
        credential = ApprovedCredential(
            "tak-1",
            public_credential([material.leaf, material.intermediate]),
            "tak-client",
            "tak-generated",
            material.leaf.not_valid_after_utc,
        )
        self.snapshot = PackageSnapshot(
            PackageSettings("test", self.principal.user_id, "tak.fixture", "FIRST"),
            (credential,),
            "tak-1",
            material.now + timedelta(hours=1),
            "approved-set-v1",
            "approved-set-v1",
            "approved-set-v1",
            material.credential,
            material.trust_pem,
            {
                "phase": "none",
                "affectedPurposes": [],
                "clientVerification": "not-required",
                "revocationState": "not-requested",
                "enforcementState": "not-applicable",
            },
        )
        self.denial: int | None = None
        self.no_certificate = False
        self.package_reads = 0
        self.on_second_read: PackageSnapshot | None = None

    async def authenticate(self, request: Request) -> Principal:
        if self.no_certificate:
            raise DeliveryError(401, "certificate-required")
        return self.principal

    async def authorize(self, user_id: UUID, credential_id: str, now: datetime) -> Principal:
        if self.denial:
            raise DeliveryError(self.denial, "access-denied" if self.denial == 403 else "authority-unavailable")
        if user_id != self.principal.user_id or credential_id != self.principal.credential_id:
            raise DeliveryError(403, "access-denied")
        return self.principal

    async def package(self, principal: Principal, profile_id: str, now: datetime) -> PackageSnapshot:
        self.package_reads += 1
        if self.on_second_read is not None and self.package_reads == 2:
            return self.on_second_read
        return self.snapshot


@dataclass
class APIFixture:
    client: TestClient
    authority: FixtureAuthority
    kubernetes: KubernetesFixture

    @property
    def package_path(self) -> str:
        return f"{PREFIX}/users/{compact_uuid(self.authority.principal.user_id)}/client-packages/atak"

    def create_grant(self) -> dict[str, str]:
        response = self.client.post(self.package_path + "/download-grants", json={})
        assert response.status_code == 201, response.text
        validate_schema(response.json(), "CreatedDownloadGrant")
        return response.json()


@pytest.fixture
def api(material: CredentialFixture) -> Iterator[APIFixture]:
    kubernetes = KubernetesFixture()
    kubernetes.put(Secret(metadata=ObjectMeta(name="tak-download-grants", namespace="tak")), "secrets")
    authority = FixtureAuthority(material)
    store = SecretGrantStore(kubernetes.async_client(Secret, "secrets"))
    with TestClient(
        create_app(authority, store, "https://core.fixture", lambda: authority.now), raise_server_exceptions=False
    ) as client:
        yield APIFixture(client, authority, kubernetes)


def test_profiles_and_live_etag(api: APIFixture) -> None:
    response = api.client.get(PREFIX + "/package-profiles")
    assert response.status_code == 200
    for item in response.json()["items"]:
        validate_schema(item, "PackageProfile")
        assert item["validatedClients"] == []
    headers = {"If-None-Match": response.headers["etag"]}
    assert api.client.get(PREFIX + "/package-profiles", headers=headers).status_code == 304
    api.authority.denial = 403
    assert api.client.get(PREFIX + "/package-profiles", headers=headers).status_code == 403


def test_metadata_and_uuid_normalization(api: APIFixture) -> None:
    response = api.client.get(api.package_path)
    validate_schema(response.json(), "ClientPackage")
    assert response.json()["state"] == "ready"
    uuid_path = api.package_path.replace(
        compact_uuid(api.authority.principal.user_id), str(api.authority.principal.user_id).upper()
    )
    assert api.client.get(uuid_path).json() == response.json()
    assert (
        api.client.get(api.package_path, headers={"If-None-Match": "W/" + response.headers["etag"]}).status_code == 304
    )
    original = response.json()["revision"]
    api.authority.snapshot = replace(
        api.authority.snapshot, settings=replace(api.authority.snapshot.settings, callsign="NEW")
    )
    changed = api.client.get(api.package_path, headers={"If-None-Match": response.headers["etag"]})
    assert changed.status_code == 200
    assert changed.json()["revision"] == original
    assert changed.json()["callsign"] == "NEW"
    api.authority.denial = 503
    assert api.client.get(api.package_path, headers={"If-None-Match": changed.headers["etag"]}).status_code == 503


@pytest.mark.parametrize("change", ["messaging", "api", "key"])
def test_pending_is_read_only(api: APIFixture, change: str) -> None:
    updates = {
        "messaging": replace(api.authority.snapshot, messaging_revision=None),
        "api": replace(api.authority.snapshot, api_revision="old"),
        "key": replace(api.authority.snapshot, material=None),
    }
    api.authority.snapshot = updates[change]
    response = api.client.get(api.package_path)
    assert response.status_code == 200
    assert response.json()["state"] == "pending"
    validate_schema(response.json(), "ClientPackage")
    assert not api.kubernetes.writes
    assert api.client.get(api.package_path + "/content").status_code == 503
    assert api.client.post(api.package_path + "/download-grants", json={}).status_code == 503


@pytest.mark.parametrize("field", ["fingerprint_sha256", "serial_hex", "issuer_id"])
def test_exact_inventory_and_authority_deadlines(api: APIFixture, field: str) -> None:
    snapshot = api.authority.snapshot
    record = snapshot.approved[0].record
    changes = {
        "fingerprint_sha256": replace(record, fingerprint_sha256="0" * 64),
        "serial_hex": replace(record, serial_hex="0" * 64),
        "issuer_id": replace(record, issuer_id="0" * 64),
    }
    api.authority.snapshot = replace(snapshot, approved=(replace(snapshot.approved[0], record=changes[field]),))
    assert api.client.get(api.package_path + "/content").status_code == 503
    api.authority.snapshot = replace(snapshot, authority_until=api.authority.now)
    assert api.client.get(api.package_path).status_code == 503


def test_degraded_metadata_remains_available(api: APIFixture) -> None:
    api.authority.snapshot = replace(api.authority.snapshot, api_revision=None, unready_state="degraded")
    response = api.client.get(api.package_path)
    assert response.status_code == 200
    assert response.json()["state"] == response.json()["takAuthorization"]["state"] == "degraded"
    validate_schema(response.json(), "ClientPackage")
    assert api.client.get(api.package_path + "/content").status_code == 503


def test_self_service_and_spoofed_identity(api: APIFixture) -> None:
    other = api.package_path.replace(compact_uuid(api.authority.principal.user_id), compact_uuid(uuid4()))
    assert api.client.get(other).status_code == 403
    api.authority.no_certificate = True
    response = api.client.get(
        api.package_path, headers={"X-User-Id": str(api.authority.principal.user_id), "X-Role": "admin"}
    )
    assert response.status_code == 401
    validate_schema(response.json(), "Problem")


@pytest.mark.parametrize(
    "query,status",
    [
        ("?variant=full&baseRevision=old", 422),
        ("?variant=unknown", 422),
        ("?variant=credential-update", 422),
        ("?variant=credential-update&baseRevision=old&compatibilityId=atak", 409),
        ("?variant=full&variant=full", 422),
        ("?token=anything", 422),
    ],
)
def test_content_selectors(api: APIFixture, query: str, status: int) -> None:
    assert api.client.get(api.package_path + "/content" + query).status_code == status


def test_content_rechecks_before_release(api: APIFixture) -> None:
    response = api.client.get(api.package_path + "/content")
    assert response.status_code == 200 and response.content.startswith(b"PK")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert api.authority.package_reads == 2
    api.authority.package_reads = 0
    api.authority.on_second_read = replace(api.authority.snapshot, api_revision="stale")
    assert api.client.get(api.package_path + "/content").status_code == 503


def test_grant_round_trip_and_latest_callsign(api: APIFixture) -> None:
    created = api.create_grant()
    management = f"{PREFIX}/download-grants/{created['id']}"
    metadata = api.client.get(management)
    assert metadata.status_code == 200
    validate_schema(metadata.json(), "DownloadGrant")
    assert "downloadUrl" not in metadata.json() and "token" not in metadata.text
    assert api.create_grant()["downloadUrl"] != created["downloadUrl"]
    token = urlsplit(created["downloadUrl"]).query.split("=", 1)[1]
    assert api.client.get(created["downloadUrl"].replace(".zip?", ".zip/?")).status_code == 404
    assert all(token not in value.model_dump_json() for value in api.kubernetes.objects.values())
    api.authority.snapshot = replace(
        api.authority.snapshot, settings=replace(api.authority.snapshot.settings, callsign="LATEST")
    )
    api.authority.no_certificate = True
    first = api.client.get(created["downloadUrl"])
    assert first.status_code == 200
    assert api.client.head(created["downloadUrl"]).status_code == 200
    assert api.client.get(created["downloadUrl"]).status_code == 200
    with ZipFile(BytesIO(first.content)) as archive:
        assert any(b"LATEST" in archive.read(name) for name in archive.namelist() if name.endswith(".pref"))
    api.authority.no_certificate = False
    assert api.client.delete(management).status_code == 204
    assert api.client.delete(management).status_code == 204
    assert api.client.get(created["downloadUrl"]).status_code == 404


@pytest.mark.parametrize(
    "change,status", [("credential", 404), ("trust", 404), ("revoked", 404), ("outage", 503), ("stale", 503)]
)
def test_redemption_freshness(api: APIFixture, change: str, status: int) -> None:
    grant = api.create_grant()
    if change == "credential":
        api.authority.snapshot = replace(api.authority.snapshot, selected_id="successor")
    elif change == "trust":
        api.authority.snapshot = replace(api.authority.snapshot, trust_pem=b"changed")
    elif change in ("revoked", "outage"):
        api.authority.denial = 403 if change == "revoked" else 503
    else:
        api.authority.snapshot = replace(api.authority.snapshot, messaging_revision="old")
    assert api.client.get(grant["downloadUrl"]).status_code == status


def test_grant_expiry_and_owner(api: APIFixture) -> None:
    api.authority.principal = replace(api.authority.principal, valid_until=api.authority.now + timedelta(seconds=60))
    created = api.create_grant()
    assert datetime.fromisoformat(created["expiresAt"]) == api.authority.principal.valid_until
    api.authority.now += timedelta(seconds=60)
    assert api.client.get(created["downloadUrl"]).status_code == 404
    api.authority.principal = replace(api.authority.principal, valid_until=api.authority.now + timedelta(hours=1))
    assert api.client.get(f"{PREFIX}/download-grants/{created['id']}").json()["state"] == "expired"
    api.authority.principal = replace(api.authority.principal, user_id=uuid4())
    assert api.client.get(f"{PREFIX}/download-grants/{created['id']}").status_code == 404
    assert api.client.delete(f"{PREFIX}/download-grants/{created['id']}").status_code == 404


@pytest.mark.parametrize(
    "suffix", ["", "?token=wrong", "?token=" + "x" * 43, "?token=" + "x" * 43 + "&variant=full", "?token=x&token=x"]
)
def test_uniform_invalid_redemption(api: APIFixture, suffix: str) -> None:
    response = api.client.get(f"{PREFIX}/downloads/{'A' * 22}/package.zip{suffix}")
    assert response.status_code == 404
    assert response.json()["code"] == "not-found"


@pytest.mark.parametrize(
    "body,status",
    [
        ({"expiresInSeconds": True}, 422),
        ({"expiresInSeconds": 301}, 422),
        ({"unknown": 1}, 422),
        ({"variant": "full", "compatibilityId": "a"}, 422),
        ({"baseRevision": None}, 422),
        ({"compatibilityId": None}, 422),
        ({"variant": "credential-update"}, 422),
        ({"variant": "credential-update", "baseRevision": "old", "compatibilityId": "id"}, 409),
    ],
)
def test_grant_body_validation(api: APIFixture, body: dict[str, object], status: int) -> None:
    assert api.client.post(api.package_path + "/download-grants", json=body).status_code == status


def test_browser_origin_and_bounded_body(api: APIFixture) -> None:
    url = api.package_path + "/download-grants"
    assert api.client.post(url, json={}, headers={"Origin": "https://attacker.fixture"}).status_code == 403
    assert api.client.post(url, json={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert api.client.post(url, content="{}", headers={"Content-Type": "text/plain"}).status_code == 422
    assert api.client.post(url, content="x" * 4097, headers={"Content-Type": "application/json"}).status_code == 422
    assert api.client.post(url, content="{", headers={"Content-Type": "application/json"}).status_code == 422
    created = api.create_grant()
    assert api.client.delete(f"{PREFIX}/download-grants/{created['id']}", headers={"Origin": "null"}).status_code == 403


def test_limits_and_storage_failure(api: APIFixture) -> None:
    for _ in range(8):
        api.create_grant()
    assert api.client.post(api.package_path + "/download-grants", json={}).status_code == 429
    api.kubernetes.failures = True
    assert api.client.get(f"{PREFIX}/download-grants/{'A' * 22}").status_code == 503


def test_render_capacity_is_bounded(api: APIFixture) -> None:
    service = PackageAPI(
        api.authority,
        SecretGrantStore(api.kubernetes.async_client(Secret, "secrets")),
        "https://core.fixture",
        lambda: api.authority.now,
    )

    async def saturated() -> None:
        for _ in range(4):
            await service.renders.acquire()
        with pytest.raises(DeliveryError) as error:
            await service.render(api.authority.snapshot, "atak")
        assert error.value.status == 429

    asyncio.run(saturated())


def test_delete_during_render_blocks_release(api: APIFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    grant = api.create_grant()
    store = SecretGrantStore(api.kubernetes.async_client(Secret, "secrets"))
    reads = 0

    async def package(principal: Principal, profile_id: str, now: datetime) -> PackageSnapshot:
        nonlocal reads
        reads += 1
        if reads == 2:
            await store.delete(grant["id"], principal.user_id)
        return api.authority.snapshot

    monkeypatch.setattr(api.authority, "package", package)
    assert api.client.get(grant["downloadUrl"]).status_code == 404


def test_unexpected_adapter_error_is_redacted(
    api: APIFixture, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    private_marker = "fixture-private-material-must-not-be-logged"

    async def authenticate(request: Request) -> Principal:
        raise RuntimeError(private_marker)

    monkeypatch.setattr(api.authority, "authenticate", authenticate)
    store = SecretGrantStore(api.kubernetes.async_client(Secret, "secrets"))
    with TestClient(create_app(api.authority, store, "https://core.fixture")) as client:
        response = client.get(PREFIX + "/package-profiles")
        assert response.status_code == 503
        assert private_marker not in response.text and private_marker not in caplog.text


def test_unknown_profiles_and_paths(api: APIFixture) -> None:
    assert api.client.get(api.package_path.replace("/atak", "/unknown")).status_code == 404
    assert api.client.get(PREFIX + "/download-grants/invalid").status_code == 404
    assert api.client.delete(PREFIX + "/download-grants/invalid").status_code == 404
    assert api.client.get(PREFIX + "/download-grants/" + "A" * 22).status_code == 404


def test_wrong_package_identity_and_material(api: APIFixture) -> None:
    snapshot = api.authority.snapshot
    api.authority.snapshot = replace(snapshot, settings=replace(snapshot.settings, user_id=uuid4()))
    assert api.client.get(api.package_path).status_code == 503
    assert snapshot.material is not None
    api.authority.snapshot = replace(snapshot, material=replace(snapshot.material, private_key_pem=b"invalid key"))
    assert api.client.get(api.package_path).status_code == 503
    assert api.client.post(api.package_path + "/download-grants", json={}).status_code == 503
    assert api.client.get(api.package_path + "/content").status_code == 503
    api.authority.snapshot = replace(
        snapshot, material=replace(snapshot.material, certificate_chain_pem=b"invalid cert")
    )
    assert api.client.get(api.package_path).status_code == 503


@pytest.mark.parametrize("change", ["trust", "host", "identity", "not-yet-valid"])
def test_unusable_inputs_never_report_ready(api: APIFixture, change: str) -> None:
    snapshot = api.authority.snapshot
    assert snapshot.material is not None
    if change == "trust":
        api.authority.snapshot = replace(snapshot, trust_pem=b"invalid CA material")
    elif change == "host":
        api.authority.snapshot = replace(snapshot, settings=replace(snapshot.settings, host="invalid host"))
    elif change == "identity":
        api.authority.snapshot = replace(snapshot, material=replace(snapshot.material, expected_user_id=uuid4()))
    else:
        api.authority.now -= timedelta(days=2)
    assert api.client.get(api.package_path).status_code == 503
    assert api.client.post(api.package_path + "/download-grants", json={}).status_code == 503


def test_default_authority_and_unknown_routes(api: APIFixture) -> None:
    store = SecretGrantStore(api.kubernetes.async_client(Secret, "secrets"))
    with TestClient(create_app(UnavailableAuthority(), store, "https://core.fixture")) as client:
        assert client.get(PREFIX + "/package-profiles", headers={"X-User-Id": str(uuid4())}).status_code == 503
        assert client.get(PREFIX + "/unknown").status_code == 404
        assert client.post(PREFIX + "/package-profiles").status_code == 405


@pytest.mark.parametrize(
    "origin",
    [
        "http://core.fixture",
        "https://user:password@core.fixture",  # pragma: allowlist secret - Reject literal fixture credentials in origins.
        "https://core.fixture/path",
        "https://core.fixture?query",
        "https://core.fixture#fragment",
        "https://",
    ],
)
def test_public_origin_validation(api: APIFixture, origin: str) -> None:
    with pytest.raises(ValueError):
        create_app(api.authority, SecretGrantStore(api.kubernetes.async_client(Secret, "secrets")), origin)


@pytest.mark.parametrize("value", ["bad", "A" * 21, "A" * 21 + "B", "../../user"])
def test_invalid_uuid(value: str) -> None:
    with pytest.raises(DeliveryError):
        parse_user_id(value)
