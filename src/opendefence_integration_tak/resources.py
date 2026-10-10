"""The Kubernetes Secret used by the grant store; Core models come from its library."""

from typing import Annotated, Literal

from cloudcoil.resources import Resource
from pydantic import Field

SecretVersion = Annotated[Literal["v1"], Field(alias="apiVersion")]


class Secret(Resource):
    """Only the v1 Secret fields used by the grant store, without a JNI extra."""

    api_version: SecretVersion = "v1"  # type: ignore[bad-override-mutable-attribute]
    kind: Literal["Secret"] = "Secret"  # type: ignore[bad-override-mutable-attribute]
    type: str = "Opaque"
    data: dict[str, str] = Field(default_factory=dict, repr=False)
