"""Kubernetes configuration with refresh of projected service-account tokens."""

from pathlib import Path

from cloudcoil.client import Config
import httpx

_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")


def cluster_config(namespace: str) -> Config:
    config = Config(namespace=namespace)
    if config.kubeconfig_path is None and _TOKEN_PATH.is_file():
        # The pinned Cloudcoil Config copies the initial in-cluster token into headers.
        def authenticate(request: httpx.Request) -> httpx.Request:
            try:
                token = _TOKEN_PATH.read_text().strip()
            except OSError:
                raise ValueError("Kubernetes service-account token is unavailable") from None
            if not token:
                raise ValueError("Kubernetes service-account token is unavailable")
            request.headers["Authorization"] = "Bearer " + token
            return request

        config.client.headers.pop("Authorization", None)
        config.async_client.headers.pop("Authorization", None)
        config.auth = authenticate
        config.client.auth = authenticate
        config.async_client.auth = authenticate
    return config
