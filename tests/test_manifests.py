"""Check that deployment overlays register a valid cluster-scoped integration."""

from pathlib import Path
import shutil
import subprocess  # nosec B404 - Render trusted repository manifests with kubectl.

import pytest
import yaml

from lib_opendefence_core.models.v1alpha1 import Integration
from opendefence_integration_tak import __version__


@pytest.mark.parametrize("overlay", ["integration", "overlays/local-dev", "overlays/production"])
def test_integration_registration(overlay: str) -> None:
    kubectl = shutil.which("kubectl")
    if kubectl is None:
        pytest.skip("kubectl is required to render deployment manifests")
    root = Path(__file__).resolve().parents[1]
    rendered = subprocess.check_output(  # nosec B603 - Fixed command and repository paths; no shell.
        [kubectl, "kustomize", str(root / "k8s" / overlay)], text=True, timeout=30
    )
    resources = list(yaml.safe_load_all(rendered))
    registrations = [item for item in resources if item["kind"] == "Integration"]
    assert len(registrations) == 1
    integration = Integration.model_validate(registrations[0])
    assert integration.name == "integration-tak"
    assert integration.namespace is None
    assert integration.spec.version == __version__
    assert integration.spec.extra_roles == []
    assert integration.status is None
    deployments = [item for item in resources if item["kind"] == "Deployment"]
    assert len(deployments) == 2
    assert all(item["metadata"]["namespace"] == "integration-tak" for item in deployments)
