"""Projected token refresh applies to both transports without a stale fallback."""

import asyncio
from pathlib import Path

import httpx
import pytest
from cloudcoil.client import Config

from opendefence_integration_tak import cluster
from tests.kubernetes import KubernetesFixture


def test_projected_token_rotation_and_loss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = KubernetesFixture()
    config = fixture.configuration(tmp_path)
    config.kubeconfig_path = None
    path = tmp_path / "projected-token"
    path.write_text("fixture-first\n")
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        return httpx.Response(200)

    config.client = httpx.Client(
        base_url="https://kubernetes.fixture",
        transport=httpx.MockTransport(handle),
        headers={"Authorization": "Bearer stale-fixture"},
    )
    config.async_client = httpx.AsyncClient(
        base_url="https://kubernetes.fixture",
        transport=httpx.MockTransport(handle),
        headers={"Authorization": "Bearer stale-fixture"},
    )

    def configured(namespace: str) -> Config:
        return config

    monkeypatch.setattr(cluster, "Config", configured)
    monkeypatch.setattr(cluster, "_TOKEN_PATH", path)
    selected = cluster.cluster_config("tak")
    selected.client.get("/fixture")
    path.write_text("fixture-successor\n")
    asyncio.run(selected.async_client.get("/fixture"))
    assert seen == ["Bearer fixture-first", "Bearer fixture-successor"]
    path.write_text("")
    with pytest.raises(ValueError, match="token is unavailable"):
        selected.client.get("/fixture")
    path.unlink()
    with pytest.raises(ValueError, match="token is unavailable"):
        asyncio.run(selected.async_client.get("/fixture"))
    assert len(seen) == 2


def test_kubeconfig_auth_is_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = KubernetesFixture().configuration(tmp_path)
    path = tmp_path / "projected-token"
    path.write_text("must-not-be-used")
    original = config.client.auth

    def configured(namespace: str) -> Config:
        return config

    monkeypatch.setattr(cluster, "Config", configured)
    monkeypatch.setattr(cluster, "_TOKEN_PATH", path)
    assert cluster.cluster_config("tak").client.auth is original
