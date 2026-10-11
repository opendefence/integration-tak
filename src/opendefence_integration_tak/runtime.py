"""Run the HTTP workload with live Kubernetes Secret access and no JVM."""

import uvicorn

from opendefence_integration_tak.api import create_app
from opendefence_integration_tak.cluster import cluster_config
from opendefence_integration_tak.delivery import UnavailableAuthority
from opendefence_integration_tak.grants import SecretGrantStore
from opendefence_integration_tak.resources import Secret


async def serve_api(namespace: str, public_origin: str) -> None:
    async with cluster_config(namespace=namespace) as config:
        client = await Secret.async_client(config, namespace=namespace)
        app = create_app(UnavailableAuthority(), SecretGrantStore(client), public_origin)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="0.0.0.0",  # nosec B104 - Container workload; Service/ingress owns access control.
                port=8080,
                access_log=False,
                proxy_headers=False,
                workers=1,
                limit_concurrency=100,
                log_level="warning",
            )
        )
        await server.serve()
