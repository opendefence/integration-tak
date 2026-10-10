"""Read the supplied Core v1alpha1 shapes; write only integration-owned bindings."""

from datetime import datetime
from typing import Annotated, Literal

from cloudcoil.resources import Resource
from pydantic import BaseModel, ConfigDict, Field

CoreVersion = Annotated[Literal["platform.opendefence.fi/v1alpha1"], Field(alias="apiVersion")]
SecretVersion = Annotated[Literal["v1"], Field(alias="apiVersion")]


class CoreModel(BaseModel):
    """Keep fields owned by Core when a resource passes through the client."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Reference(CoreModel):
    name: str


class UserSpec(CoreModel):
    callsign: str
    approved_at: datetime | None = Field(default=None, alias="approvedAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    role_refs: list[Reference] = Field(default_factory=list, alias="roleRefs")
    group_refs: list[Reference] = Field(default_factory=list, alias="groupRefs")


class User(Resource):
    # Cloudcoil declares mutable Any GVK fields; each concrete wire kind must narrow them.
    api_version: CoreVersion = "platform.opendefence.fi/v1alpha1"  # type: ignore[bad-override-mutable-attribute]
    kind: Literal["User"] = "User"  # type: ignore[bad-override-mutable-attribute]
    spec: UserSpec
    status: CoreModel | None = None


class GroupSpec(CoreModel):
    name: str
    display_name: str = Field(alias="displayName")
    parent_ref: Reference | None = Field(default=None, alias="parentRef")
    role_refs: list[Reference] = Field(default_factory=list, alias="roleRefs")
    manager_refs: list[Reference] = Field(default_factory=list, alias="managerRefs")


class Group(Resource):
    api_version: CoreVersion = "platform.opendefence.fi/v1alpha1"  # type: ignore[bad-override-mutable-attribute]
    kind: Literal["Group"] = "Group"  # type: ignore[bad-override-mutable-attribute]
    spec: GroupSpec
    status: CoreModel | None = None


class RoleSpec(CoreModel):
    name: str
    display_name: str = Field(alias="displayName")


class Role(Resource):
    api_version: CoreVersion = "platform.opendefence.fi/v1alpha1"  # type: ignore[bad-override-mutable-attribute]
    kind: Literal["Role"] = "Role"  # type: ignore[bad-override-mutable-attribute]
    spec: RoleSpec
    status: CoreModel | None = None


class BindingSpec(CoreModel):
    user_ref: Reference = Field(alias="userRef")


class Condition(CoreModel):
    type: str
    status: Literal["True", "False", "Unknown"]
    reason: str
    message: str
    last_transition_time: datetime = Field(alias="lastTransitionTime")
    observed_generation: int | None = Field(default=None, alias="observedGeneration")


class BindingStatus(CoreModel):
    conditions: list[Condition] = Field(default_factory=list)
    observed_generation: int | None = Field(default=None, alias="observedGeneration")


class UserBinding(Resource):
    api_version: CoreVersion = "platform.opendefence.fi/v1alpha1"  # type: ignore[bad-override-mutable-attribute]
    kind: Literal["UserBinding"] = "UserBinding"  # type: ignore[bad-override-mutable-attribute]
    spec: BindingSpec
    status: BindingStatus | None = None


class Secret(Resource):
    """Only the v1 Secret fields used by the grant store, without a JNI extra."""

    api_version: SecretVersion = "v1"  # type: ignore[bad-override-mutable-attribute]
    kind: Literal["Secret"] = "Secret"  # type: ignore[bad-override-mutable-attribute]
    type: str = "Opaque"
    data: dict[str, str] = Field(default_factory=dict, repr=False)
