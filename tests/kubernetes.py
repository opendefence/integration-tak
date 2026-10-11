"""A Kubernetes HTTP fixture with independent UID and resourceVersion checks."""

import json
from threading import Lock
from pathlib import Path

from cloudcoil.client import APIClient, AsyncAPIClient, Config
from cloudcoil.resources import Resource
import httpx

from lib_opendefence_core.models.v1alpha1 import UserBinding


class KubernetesFixture:
    def __init__(self) -> None:
        self.objects: dict[str, Resource] = {}
        self.writes: list[tuple[str, Resource]] = []
        self.conflicts = 0
        self.failures = False
        self.lock = Lock()

    def put(self, resource: Resource, plural: str) -> None:
        assert resource.metadata is not None and resource.name
        resource.metadata.uid = resource.metadata.uid or f"uid-{resource.name}"
        resource.metadata.resource_version = "1"
        resource.metadata.generation = 1
        base = "/api/v1" if resource.api_version == "v1" else f"/apis/{resource.api_version}"
        namespace = f"/namespaces/{resource.namespace}" if resource.namespace else ""
        self.objects[f"{base}{namespace}/{plural}/{resource.name}"] = resource.model_copy(deep=True)

    def handle(self, request: httpx.Request) -> httpx.Response:
        with self.lock:
            return self._handle(request)

    def _handle(self, request: httpx.Request) -> httpx.Response:  # noqa: PLR0911, PLR0912 - Fixture HTTP dispatcher.
        if self.failures:
            return httpx.Response(503, json={"message": "fixture unavailable"})
        path = request.url.path
        if path == "/version":
            return httpx.Response(200, json={"major": "1", "minor": "35"})
        if path == "/api":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "metadata": {"name": ""},
                            "versions": [
                                {
                                    "version": "v1",
                                    "resources": [
                                        {
                                            "resource": "secrets",
                                            "responseKind": {"kind": "Secret"},
                                            "scope": "Namespaced",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
            )
        if path == "/apis":
            kinds = [
                ("User", "users", False),
                ("Group", "groups", False),
                ("Role", "roles", False),
                ("UserBinding", "userbindings", True),
            ]
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "metadata": {"name": "platform.opendefence.fi"},
                            "versions": [
                                {
                                    "version": "v1alpha1",
                                    "resources": [
                                        {
                                            "responseKind": {"kind": kind},
                                            "resource": plural,
                                            "scope": "Namespaced" if namespaced else "Cluster",
                                            "subresources": [{"subresource": "status"}],
                                        }
                                        for kind, plural, namespaced in kinds
                                    ],
                                }
                            ],
                        }
                    ]
                },
            )
        status_path = path.endswith("/status")
        path = path.removesuffix("/status")
        resource = self.objects.get(path)
        if request.method == "GET":
            if resource:
                return httpx.Response(200, json=resource.model_dump(mode="json", by_alias=True, exclude_none=True))
            items = [
                value.model_dump(mode="json", by_alias=True, exclude_none=True)
                for key, value in self.objects.items()
                if key.rsplit("/", 1)[0] == path
            ]
            if items or path.endswith(("/users", "/groups", "/roles", "/userbindings")):
                return httpx.Response(
                    200,
                    json={
                        "apiVersion": "platform.opendefence.fi/v1alpha1",
                        "kind": {
                            "users": "UserList",
                            "groups": "GroupList",
                            "roles": "RoleList",
                            "userbindings": "UserBindingList",
                        }[path.rsplit("/", 1)[-1]],
                        "metadata": {"resourceVersion": "1"},
                        "items": items,
                    },
                )
            return httpx.Response(404, json={"message": "not found"})
        body = json.loads(request.content)
        if request.method == "POST":
            created = UserBinding.model_validate(body)
            target = path + "/" + (created.name or "")
            if target in self.objects:
                return httpx.Response(409, json={"message": "already exists"})
            self.put(created, "userbindings")
            self.writes.append(("create", created.model_copy(deep=True)))
            return httpx.Response(
                201, json=self.objects[target].model_dump(mode="json", by_alias=True, exclude_none=True)
            )
        if request.method == "PUT" and resource and resource.metadata:
            if self.conflicts:
                self.conflicts -= 1
                return httpx.Response(409, json={"message": "conflict"})
            updated = type(resource).model_validate(body)
            assert updated.metadata is not None
            if updated.metadata.resource_version != resource.metadata.resource_version:
                return httpx.Response(409, json={"message": "conflict"})
            assert updated.metadata.uid == resource.metadata.uid
            updated.metadata.resource_version = str(int(resource.metadata.resource_version or "0") + 1)
            if status_path:
                preserved = resource.model_copy(deep=True)
                assert preserved.metadata is not None
                preserved.metadata.resource_version = updated.metadata.resource_version
                assert isinstance(updated, UserBinding) and isinstance(preserved, UserBinding)
                preserved.status = updated.status
                updated = preserved
            self.objects[path] = updated.model_copy(deep=True)
            self.writes.append(("status" if status_path else "update", updated.model_copy(deep=True)))
            return httpx.Response(200, json=updated.model_dump(mode="json", by_alias=True, exclude_none=True))
        raise AssertionError(f"Unexpected Kubernetes fixture method {request.method}")

    def sync_client[T: Resource](self, kind: type[T], plural: str, namespace: str = "") -> APIClient[T]:
        return APIClient(
            kind.gvk().api_version,
            kind,
            plural,
            ["status"],
            namespace,
            bool(namespace),
            httpx.Client(base_url="https://kubernetes.fixture", transport=httpx.MockTransport(self.handle)),
        )

    def async_client[T: Resource](self, kind: type[T], plural: str, namespace: str = "tak") -> AsyncAPIClient[T]:
        return AsyncAPIClient(
            kind.gvk().api_version,
            kind,
            plural,
            [],
            namespace,
            True,
            httpx.AsyncClient(base_url="https://kubernetes.fixture", transport=httpx.MockTransport(self.handle)),
        )

    def configuration(self, directory: Path) -> Config:
        path = directory / "kubeconfig.json"
        path.write_text(
            json.dumps(
                {
                    "clusters": [{"name": "fixture", "cluster": {"server": "https://kubernetes.fixture"}}],
                    "contexts": [
                        {"name": "fixture", "context": {"cluster": "fixture", "user": "fixture", "namespace": "tak"}}
                    ],
                    "users": [{"name": "fixture", "user": {}}],
                    "current-context": "fixture",
                }
            )
        )
        config = Config(kubeconfig=path)
        config.client = httpx.Client(base_url="https://kubernetes.fixture", transport=httpx.MockTransport(self.handle))
        config.async_client = httpx.AsyncClient(
            base_url="https://kubernetes.fixture", transport=httpx.MockTransport(self.handle)
        )
        return config
