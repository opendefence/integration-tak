"""Use actual Cloudcoil HTTP clients to test binding ownership and freshness."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from datetime import tzinfo

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.errors import APIError
import pytest
import httpx

from opendefence_integration_tak import operator

from opendefence_integration_tak.operator import (
    BindingReconciler,
    ProjectionReceipt,
    UnavailableProjector,
    binding_name,
    input_revision,
    set_condition,
)
from opendefence_integration_tak.resources import (
    BindingSpec,
    BindingStatus,
    Condition,
    CoreModel,
    Group,
    GroupSpec,
    Reference,
    Role,
    RoleSpec,
    User,
    UserBinding,
    UserSpec,
)
from tests.kubernetes import KubernetesFixture


def core_user() -> User:
    return User(metadata=ObjectMeta(name="person", uid="original-user", generation=1), spec=UserSpec(callsign="FIRST"))


class FixtureProjector:
    def __init__(self) -> None:
        self.receipt: ProjectionReceipt | None = None
        self.failure = False
        self.mutate: User | None = None

    def reconcile(self, user: User, groups: list[Group], roles: list[Role], revision: str) -> ProjectionReceipt:
        if self.failure:
            raise RuntimeError("fixture partial write")
        if self.mutate is not None:
            self.mutate.spec.callsign = "CHANGED"
        return self.receipt or ProjectionReceipt(
            revision, "strict-v1", "strict-v1", "strict-v1", datetime.now(UTC) + timedelta(minutes=5)
        )


def reconciler(projector: FixtureProjector | UnavailableProjector) -> tuple[BindingReconciler, KubernetesFixture, User]:
    fixture = KubernetesFixture()
    user = core_user()
    fixture.put(user, "users")
    return (
        BindingReconciler(
            fixture.sync_client(User, "users"),
            fixture.sync_client(Group, "groups"),
            fixture.sync_client(Role, "roles"),
            fixture.sync_client(UserBinding, "userbindings", "tak"),
            projector,
        ),
        fixture,
        user,
    )


def condition(binding: UserBinding) -> Condition:
    assert binding.status is not None
    return next(item for item in binding.status.conditions if item.type == "Synced")


def test_unavailable_authority_and_idempotency() -> None:
    worker, fixture, user = reconciler(UnavailableProjector())
    binding = worker.reconcile(user, [], [])
    assert condition(binding).status == "False"
    assert condition(binding).reason == "AuthorityUnavailable"
    assert binding.spec.user_ref.name == user.name
    assert binding.metadata and binding.metadata.owner_references and user.metadata
    assert binding.metadata.owner_references[0].uid == user.metadata.uid
    writes = len(fixture.writes)
    worker.reconcile(user, [], [])
    assert len(fixture.writes) == writes


def test_full_readback_and_refresh() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    binding = worker.reconcile(user, [], [])
    assert condition(binding).status == "True"
    assert condition(binding).observed_generation == 1
    assert len(fixture.writes) == 5
    assert binding.metadata and binding.metadata.annotations
    assert binding.metadata.annotations["integration.opendefence.fi/applied-revision"] == "strict-v1"
    projector.receipt = ProjectionReceipt(
        input_revision(user, [], []), "strict-v2", "strict-v2", "strict-v1", datetime.now(UTC) + timedelta(minutes=5)
    )
    assert condition(worker.reconcile(user, [], [])).status == "False"


@pytest.mark.parametrize("change", ["input", "api", "messaging", "expiry", "naive", "empty"])
def test_unverified_receipts_never_mark_ready(change: str) -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    receipt = ProjectionReceipt(
        input_revision(user, [], []), "rev", "rev", "rev", datetime.now(UTC) + timedelta(minutes=5)
    )
    updates = {
        "input": replace(receipt, input_revision="old"),
        "api": replace(receipt, api_revision="old"),
        "messaging": replace(receipt, messaging_revision="old"),
        "expiry": replace(receipt, valid_until=datetime.now(UTC)),
        "naive": replace(receipt, valid_until=datetime.now()),
        "empty": replace(receipt, desired_revision=""),
    }
    projector.receipt = updates[change]
    assert condition(worker.reconcile(user, [], [])).reason == "ProjectionUnverified"


def test_partial_failure_clears_synced() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    worker.reconcile(user, [], [])
    projector.failure = True
    with pytest.raises(RuntimeError):
        worker.reconcile(user, [], [])
    binding = next(resource for resource in fixture.objects.values() if isinstance(resource, UserBinding))
    assert condition(binding).reason == "ProjectionFailed"
    assert condition(binding).status == "False"


def test_user_changes_during_projection() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    stored = next(resource for resource in fixture.objects.values() if isinstance(resource, User))
    projector.mutate = stored
    assert condition(worker.reconcile(user, [], [])).reason == "InputsChanged"


def test_receipt_expires_during_core_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    tick = datetime.now(UTC)
    projector.receipt = ProjectionReceipt(
        input_revision(user, [], []), "rev", "rev", "rev", tick + timedelta(seconds=30)
    )

    class Clock:
        @staticmethod
        def now(tz: tzinfo | None = None) -> datetime:
            return tick

    handle = fixture._handle

    def delayed(request: httpx.Request) -> httpx.Response:
        nonlocal tick
        if request.url.path.endswith("/users/person"):
            tick += timedelta(minutes=1)
        return handle(request)

    monkeypatch.setattr(operator, "datetime", Clock)
    monkeypatch.setattr(fixture, "_handle", delayed)
    assert condition(worker.reconcile(user, [], [])).reason == "ProjectionUnverified"


def test_recreated_user_gets_new_binding() -> None:
    worker, fixture, user = reconciler(UnavailableProjector())
    original = worker.reconcile(user, [], [])
    assert user.metadata is not None
    user.metadata.uid = "replacement-user"
    replacement = worker.reconcile(user, [], [])
    assert original.name != replacement.name
    assert len([item for item in fixture.objects.values() if isinstance(item, UserBinding)]) == 2


@pytest.mark.parametrize("change", ["label", "owner", "reference"])
def test_foreign_binding_is_preserved(change: str) -> None:
    worker, fixture, user = reconciler(UnavailableProjector())
    binding = worker.reconcile(user, [], [])
    assert binding.metadata is not None
    if change == "label":
        binding.metadata.labels = {"app.kubernetes.io/managed-by": "somebody-else"}
    elif change == "owner":
        binding.metadata.owner_references = []
    else:
        binding.spec.user_ref.name = "other"
    fixture.put(binding, "userbindings")
    writes = len(fixture.writes)
    with pytest.raises(ValueError, match="ownership conflict"):
        worker.reconcile(user, [], [])
    assert len(fixture.writes) == writes


def test_input_revisions_ignore_binding_feedback_and_track_references() -> None:
    user = core_user()
    user.status = CoreModel(publicKey="current", bindings=[{"synced": False}])
    original = input_revision(user, [], [])
    user.status = CoreModel(publicKey="current", bindings=[{"synced": True}])
    assert input_revision(user, [], []) == original
    group = Group(metadata=ObjectMeta(name="group", uid="group-uid"), spec=GroupSpec(name="group", displayName="Group"))
    role = Role(metadata=ObjectMeta(name="role", uid="role-uid"), spec=RoleSpec(name="role", displayName="Role"))
    revision = input_revision(user, [group], [role])
    group.spec.parent_ref = Reference(name="parent")
    assert input_revision(user, [group], [role]) != revision
    role.spec.display_name = "Changed role"
    assert input_revision(user, [group], [role]) != original


def test_conditions_preserve_other_writers_and_transition_time() -> None:
    now = datetime.now(UTC)
    other = Condition(type="Other", status="True", reason="Okay", message="Okay", lastTransitionTime=now)
    binding = UserBinding(
        metadata=ObjectMeta(generation=1),
        spec=BindingSpec(userRef=Reference(name="person")),
        status=BindingStatus(conditions=[other]),
    )
    assert set_condition(binding, False, "Unavailable", now)
    assert not set_condition(binding, False, "Unavailable", now + timedelta(seconds=1))
    assert set_condition(binding, False, "ChangedReason", now + timedelta(seconds=2))
    assert condition(binding).last_transition_time == now
    assert set_condition(binding, True, "Okay", now + timedelta(seconds=3))
    assert condition(binding).last_transition_time == now + timedelta(seconds=3)
    assert binding.status and other in binding.status.conditions


def test_scan_and_conflict_retry() -> None:
    worker, fixture, _ = reconciler(UnavailableProjector())
    fixture.conflicts = 1
    worker.run_once()
    worker.run_once()
    binding = next(resource for resource in fixture.objects.values() if isinstance(resource, UserBinding))
    assert condition(binding).reason == "AuthorityUnavailable"
    fixture.failures = True
    with pytest.raises(APIError):
        worker.run_once()


def test_missing_resource_identity() -> None:
    user = User(spec=UserSpec(callsign="Test"))
    with pytest.raises(ValueError):
        binding_name(user)
    with pytest.raises(ValueError):
        input_revision(user, [], [])
