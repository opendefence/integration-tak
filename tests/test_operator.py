"""Use actual Cloudcoil HTTP clients to test binding ownership and freshness."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from datetime import tzinfo
import json

from cloudcoil.apimachinery import ObjectMeta, Time
from cloudcoil.errors import APIError
import pytest
import httpx

from opendefence_integration_tak import operator
from opendefence_integration_tak.certificates import ACCEPTED_CREDENTIALS_ANNOTATION, PublicCredential

from opendefence_integration_tak.operator import (
    BindingReconciler,
    CredentialGrant,
    CredentialProjection,
    ProjectionReceipt,
    ProjectionUnavailable,
    UnavailableProjector,
    binding_name,
    input_revision,
    projected_tak_role,
    set_condition,
)
from lib_opendefence_core.models.v1alpha1 import (
    BindingObservation,
    Group,
    GroupSpec,
    ObjectRef,
    Role,
    RoleSpec,
    User,
    UserBinding,
    UserBindingSpec,
    UserBindingStatus,
    UserSpec,
    UserStatus,
)
from lib_opendefence_core.models.v1alpha1.common import PlatformCondition, ResolvedRef
from tests.kubernetes import KubernetesFixture


def core_user() -> User:
    now = datetime.now(UTC)
    credentials = json.dumps(
        {
            "version": 1,
            "credentials": [
                {
                    "fingerprintSha256": "a" * 64,
                    "serialHex": "1",
                    "issuerId": "issuer-sha256:" + "b" * 64,
                    "notBefore": (now - timedelta(days=1)).isoformat(),
                    "notAfter": (now + timedelta(days=1)).isoformat(),
                }
            ],
        }
    )
    return User(
        kind="User",
        metadata=ObjectMeta(
            name="person",
            uid="original-user",
            generation=1,
            annotations={ACCEPTED_CREDENTIALS_ANNOTATION: credentials},
        ),
        spec=UserSpec(callsign="first", approvedAt=now - timedelta(hours=1)),
        status=UserStatus(observedGeneration=1),
    )


class FixtureProjector:
    def __init__(self) -> None:
        self.receipt: ProjectionReceipt | None = None
        self.failure = False
        self.mutate: User | None = None
        self.seen_previous: list[tuple[PublicCredential, ...]] = []
        self.seen_credentials: list[tuple[CredentialGrant, ...]] = []

    def reconcile(
        self,
        user: User,
        groups: list[Group],
        roles: list[Role],
        credentials: CredentialProjection,
        revision: str,
    ) -> ProjectionReceipt:
        self.seen_previous.append(credentials.previous)
        self.seen_credentials.append(credentials.desired)
        if self.failure:
            raise RuntimeError("fixture partial write")
        if self.mutate is not None:
            self.mutate.spec.callsign = "changed"
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


def condition(binding: UserBinding) -> PlatformCondition:
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


def test_projected_roles_drive_tak_roles_without_core_operator() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    now = datetime.now(UTC)
    user.spec.role_refs = [ObjectRef(name="superadmin")]
    assert projected_tak_role(user, now) == "ROLE_READONLY"
    fixture.put(user, "users")
    assert condition(worker.reconcile(user, [], [])).status == "True"
    assert projector.seen_credentials[-1][0].tak_role == "ROLE_READONLY"

    assert user.status is not None
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    fixture.put(user, "users")
    assert condition(worker.reconcile(user, [], [])).status == "True"
    assert projector.seen_credentials[-1][0].tak_role == "ROLE_ADMIN"
    assert projector.seen_credentials[-1][0].credential.fingerprint_sha256 == "a" * 64
    assert projector.seen_credentials[-1][0].credential.serial_hex == "1"

    assert user.metadata is not None and user.metadata.annotations is not None
    accepted = user.metadata.annotations.pop(ACCEPTED_CREDENTIALS_ANNOTATION)
    fixture.put(user, "users")
    assert condition(worker.reconcile(user, [], [])).status == "False"
    assert projector.seen_previous[-1][0].fingerprint_sha256 == "a" * 64
    assert projector.seen_credentials[-1] == ()

    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = accepted
    user.status.roles = []
    fixture.put(user, "users")
    assert condition(worker.reconcile(user, [], [])).status == "True"
    assert projector.seen_credentials[-1][0].tak_role == "ROLE_READONLY"

    assert user.metadata is not None
    user.metadata.generation = 2
    with pytest.raises(ProjectionUnavailable):
        projected_tak_role(user, now)
    assert condition(worker.reconcile(user, [], [])).status == "False"
    assert projector.seen_credentials[-1][0].tak_role == "ROLE_READONLY"

    user.spec.revoked_at = now
    assert projected_tak_role(user, now) is None
    assert condition(worker.reconcile(user, [], [])).status == "False"
    assert projector.seen_credentials[-1] == ()


def test_certificate_rollover_preserves_one_user_binding_and_role() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    assert user.status is not None and user.metadata is not None and user.metadata.annotations is not None
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    fixture.put(user, "users")
    original = worker.reconcile(user, [], [])
    accepted = json.loads(user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION])
    replacement = accepted["credentials"][0] | {"fingerprintSha256": "b" * 64, "serialHex": "2"}
    accepted["credentials"].append(replacement)
    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = json.dumps(accepted)
    fixture.put(user, "users")

    overlap = worker.reconcile(user, [], [])
    assert overlap.name == original.name
    assert condition(overlap).status == "True"
    assert {grant.credential.fingerprint_sha256 for grant in projector.seen_credentials[-1]} == {"a" * 64, "b" * 64}
    assert {grant.tak_role for grant in projector.seen_credentials[-1]} == {"ROLE_ADMIN"}

    accepted["credentials"] = [replacement]
    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = json.dumps(accepted)
    fixture.put(user, "users")
    renewed = worker.reconcile(user, [], [])
    assert renewed.name == original.name
    assert condition(renewed).status == "True"
    assert {record.fingerprint_sha256 for record in projector.seen_previous[-1]} == {"a" * 64, "b" * 64}
    assert [(grant.credential.fingerprint_sha256, grant.tak_role) for grant in projector.seen_credentials[-1]] == [
        ("b" * 64, "ROLE_ADMIN")
    ]
    assert len([item for item in fixture.objects.values() if isinstance(item, UserBinding)]) == 1
    assert renewed.metadata is not None and renewed.metadata.annotations is not None
    applied = json.loads(renewed.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert [(item["fingerprintSha256"], item["serialHex"]) for item in applied["credentials"]] == [("b" * 64, "2")]


def test_full_readback_and_refresh() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    binding = worker.reconcile(user, [], [])
    assert condition(binding).status == "True"
    assert condition(binding).observed_generation == 1
    assert len(fixture.writes) == 5
    assert binding.metadata and binding.metadata.annotations
    assert binding.metadata.annotations["integration.opendefence.fi/applied-revision"] == "strict-v1"
    saved = json.loads(binding.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert saved["credentials"][0]["fingerprintSha256"] == "a" * 64
    projector.receipt = ProjectionReceipt(
        input_revision(user, [], []), "strict-v2", "strict-v2", "strict-v1", datetime.now(UTC) + timedelta(minutes=5)
    )
    assert condition(worker.reconcile(user, [], [])).status == "False"


@pytest.mark.parametrize("change", ["input", "api", "messaging", "expiry", "naive", "empty", "beyond-credential"])
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
        "beyond-credential": replace(receipt, valid_until=datetime.now(UTC) + timedelta(days=2)),
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
    observation = BindingObservation(name="binding", namespace="tak", uid="binding-uid", synced=False)
    user.status = UserStatus(publicKey="current", bindings=[observation], observedGeneration=1)
    original = input_revision(user, [], [])
    user.status = UserStatus(
        publicKey="current",
        bindings=[observation.model_copy(update={"synced": True})],
        observedGeneration=2,
        conditions=[
            PlatformCondition(
                type="BindingsSynced",
                status="True",
                reason="Synced",
                message="Synced",
                lastTransitionTime=Time(datetime.now(UTC)),
            )
        ],
    )
    assert input_revision(user, [], []) == original
    assert user.metadata is not None and user.metadata.annotations is not None
    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = user.metadata.annotations[
        ACCEPTED_CREDENTIALS_ANNOTATION
    ].replace('"serialHex": "1"', '"serialHex": "2"')
    assert input_revision(user, [], []) != original
    original = input_revision(user, [], [])
    user.status.public_key = "changed"
    assert input_revision(user, [], []) != original
    group = Group(
        kind="Group",
        metadata=ObjectMeta(name="group", uid="group-uid"),
        spec=GroupSpec(name="group", displayName="Group"),
    )
    role = Role(
        kind="Role", metadata=ObjectMeta(name="role", uid="role-uid"), spec=RoleSpec(name="role", displayName="Role")
    )
    revision = input_revision(user, [group], [role])
    group.spec.parent_ref = ObjectRef(name="parent")
    assert input_revision(user, [group], [role]) != revision
    revision = input_revision(user, [group], [role])
    role.spec.display_name = "Changed role"
    assert input_revision(user, [group], [role]) != revision


def test_conditions_preserve_other_writers_and_transition_time() -> None:
    now = datetime.now(UTC)
    other = PlatformCondition(type="Other", status="True", reason="Okay", message="Okay", lastTransitionTime=Time(now))
    binding = UserBinding(
        kind="UserBinding",
        metadata=ObjectMeta(generation=1),
        spec=UserBindingSpec(userRef=ObjectRef(name="person")),
        status=UserBindingStatus(conditions=[other]),
    )
    assert set_condition(binding, False, "Unavailable", now)
    assert not set_condition(binding, False, "Unavailable", now + timedelta(seconds=1))
    assert set_condition(binding, False, "ChangedReason", now + timedelta(seconds=2))
    assert condition(binding).last_transition_time.root == now
    assert set_condition(binding, True, "Okay", now + timedelta(seconds=3))
    assert condition(binding).last_transition_time.root == now + timedelta(seconds=3)
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
    user = User(kind="User", spec=UserSpec(callsign="test"))
    with pytest.raises(ValueError):
        binding_name(user)
    with pytest.raises(ValueError):
        input_revision(user, [], [])


@pytest.mark.parametrize("raw", [None, "", "{}", '{"version":1,"credentials":[]}', "not-json"])
def test_missing_or_malformed_credential_metadata_keeps_binding_unready(raw: str | None) -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    assert user.metadata is not None
    user.metadata.annotations = {ACCEPTED_CREDENTIALS_ANNOTATION: raw} if raw is not None else {}
    assert condition(worker.reconcile(user, [], [])).reason == "CredentialsUnavailable"
    assert projector.seen_credentials == [()]


def test_removed_credentials_reach_projector_before_binding_stays_unready() -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    assert condition(worker.reconcile(user, [], [])).status == "True"
    assert user.metadata is not None
    user.metadata.annotations = {}
    revision = input_revision(user, [], [])
    projector.receipt = ProjectionReceipt(
        revision, "strict-v2", "strict-v2", "old", datetime.now(UTC) + timedelta(minutes=5)
    )
    assert condition(worker.reconcile(user, [], [])).reason == "ProjectionUnverified"
    binding = worker.bindings.get(binding_name(user), "tak")
    assert binding.metadata and binding.metadata.annotations
    saved = json.loads(binding.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert saved["credentials"][0]["fingerprintSha256"] == "a" * 64
    projector.receipt = None
    assert condition(worker.reconcile(user, [], [])).status == "False"
    assert projector.seen_previous[-1] == tuple(grant.credential for grant in projector.seen_credentials[0])
    assert projector.seen_credentials[-1] == ()
    binding = worker.bindings.get(binding_name(user), "tak")
    assert binding.metadata and binding.metadata.annotations
    saved = json.loads(binding.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert saved["credentials"] == []


def test_applied_credentials_survive_reconciler_restart() -> None:
    first = FixtureProjector()
    worker, _, user = reconciler(first)
    worker.reconcile(user, [], [])
    restarted = BindingReconciler(worker.users, worker.groups, worker.roles, worker.bindings, FixtureProjector())
    assert user.metadata is not None
    user.metadata.annotations = {}
    assert condition(restarted.reconcile(user, [], [])).reason == "CredentialsUnavailable"
    assert isinstance(restarted.projector, FixtureProjector)
    assert restarted.projector.seen_previous[-1] == tuple(grant.credential for grant in first.seen_credentials[0])


def test_invalid_applied_state_recovers_from_verified_projection() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    worker.reconcile(user, [], [])
    binding = next(resource for resource in fixture.objects.values() if isinstance(resource, UserBinding))
    assert binding.metadata and binding.metadata.annotations
    binding.metadata.annotations["integration.opendefence.fi/applied-credentials"] = "broken"
    fixture.put(binding, "userbindings")
    worker.projector = UnavailableProjector()
    assert condition(worker.reconcile(user, [], [])).reason == "AuthorityUnavailable"
    assert binding.metadata.annotations["integration.opendefence.fi/applied-credentials"] == "broken"
    worker.projector = projector
    assert condition(worker.reconcile(user, [], [])).reason == "ProjectionVerified"
    assert projector.seen_previous[-1] == ()
    updated = worker.bindings.get(binding_name(user), "tak")
    assert updated.metadata and updated.metadata.annotations
    assert updated.metadata.annotations["integration.opendefence.fi/applied-credentials"] != "broken"


@pytest.mark.parametrize("change", ["unapproved", "revoked"])
def test_user_approval_state_removes_credential_access(change: str) -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    assert condition(worker.reconcile(user, [], [])).status == "True"
    if change == "unapproved":
        user.spec.approved_at = None
    else:
        user.spec.revoked_at = datetime.now(UTC)
    assert condition(worker.reconcile(user, [], [])).status == "False"
    assert projector.seen_credentials[-1] == ()
