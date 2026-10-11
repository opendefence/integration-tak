"""Exercise workload launch through discovery with no live cluster or JVM."""

import asyncio
from pathlib import Path
import sys

from cloudcoil.client import Config
import httpx
import pytest
import uvicorn
from starlette.applications import Starlette

from opendefence_integration_tak import console, operator, runtime
from opendefence_integration_tak.api import PREFIX
from opendefence_integration_tak.certificates import PublicCredential
from lib_opendefence_core.models.v1alpha1 import UserBinding
from tests.kubernetes import KubernetesFixture
from tests.test_operator import core_user, condition


def test_api_runtime_discovery_and_safe_server_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = KubernetesFixture()
    config = fixture.configuration(tmp_path)

    def configured(*, namespace: str) -> Config:
        assert namespace == "tak"
        return config

    async def serve(server: uvicorn.Server) -> None:
        assert server.config.workers == 1
        assert not server.config.access_log
        assert not server.config.proxy_headers
        assert server.config.port == 8080
        assert isinstance(server.config.app, Starlette)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.config.app), base_url="https://core.fixture"
        ) as client:
            response = await client.get(PREFIX + "/package-profiles")
            assert response.status_code == 503
            assert response.json()["code"] == "authority-unavailable"

    monkeypatch.setattr(runtime, "cluster_config", configured)
    monkeypatch.setattr(uvicorn.Server, "serve", serve)
    asyncio.run(runtime.serve_api("tak", "https://core.fixture"))
    assert not fixture.writes
    assert "jnius" not in sys.modules


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("connection_failure", [False, True])
def test_operator_runtime_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool, connection_failure: bool
) -> None:
    fixture = KubernetesFixture()
    fixture.put(core_user(), "users")
    config = fixture.configuration(tmp_path)
    # Complete discovery before simulating a Core scan outage.
    config.initialize()
    fixture.failures = failure

    def configured(*, namespace: str) -> Config:
        assert namespace == "tak"
        return config

    def stop(seconds: float) -> None:
        assert seconds == 10
        raise KeyboardInterrupt

    monkeypatch.setattr(operator, "cluster_config", configured)
    monkeypatch.setattr(operator.time, "sleep", stop)

    def missing_path(_name: str) -> Path:
        return tmp_path / "missing"

    monkeypatch.setattr(operator, "Path", missing_path)
    jni_calls: list[str] = []

    class TakFixture:
        def start(self) -> None:
            jni_calls.append("start")

        def check(self) -> None:
            jni_calls.append("check")

        def reconcile_user(
            self, user_uid: str, credentials: tuple[PublicCredential, ...], role: str | None, groups: tuple[str, ...]
        ) -> None:
            assert user_uid == "original-user"
            assert len(credentials) == 1 and credentials[0].fingerprint_sha256 == "a" * 64
            assert role == "ROLE_READONLY" and groups == ()
            jni_calls.append("project")

        def close(self) -> None:
            jni_calls.append("close")

        def reconcile_connections(self) -> None:
            jni_calls.append("connections")
            if connection_failure:
                raise ConnectionError("unavailable")

    monkeypatch.setattr(operator, "TakJvmRuntime", TakFixture)
    with pytest.raises(KeyboardInterrupt):
        operator.run_operator("tak")
    assert jni_calls == (
        ["start", "check", "connections", "close"] if failure else ["start", "check", "project", "connections", "close"]
    )
    if not failure:
        binding = next(item for item in fixture.objects.values() if isinstance(item, UserBinding))
        assert condition(binding).reason == "EnforcementUnverified"
    assert "jnius" not in sys.modules


@pytest.mark.parametrize("command", ["api", "operator"])
def test_console_workloads(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    calls: list[str] = []

    async def api(namespace: str, public_origin: str) -> None:
        assert namespace == "tak" and public_origin == "https://core.fixture"
        calls.append("api")

    def reconcile(namespace: str) -> None:
        assert namespace == "tak"
        calls.append("operator")

    arguments = ["integration", command, "--namespace", "tak"]
    if command == "api":
        arguments += ["--public-origin", "https://core.fixture"]
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setattr(console, "serve_api", api)
    monkeypatch.setattr(console, "run_operator", reconcile)
    console.main()
    assert calls == [command]
