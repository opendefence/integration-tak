"""Use actual Cloudcoil HTTP clients to test binding ownership and freshness."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from datetime import tzinfo
import json
from unittest.mock import MagicMock

from cloudcoil.apimachinery import ObjectMeta, Time
from cloudcoil.errors import APIError
import pytest
import httpx

from opendefence_integration_tak import operator
from opendefence_integration_tak.certificates import ACCEPTED_CREDENTIALS_ANNOTATION, PublicCredential

from opendefence_integration_tak.operator import (
    BindingReconciler,
    JniProjector,
    Projector,
    ProjectionReceipt,
    ProjectionUnavailable,
    UnavailableProjector,
    UserProjection,
    binding_name,
    input_revision,
    projected_tak_role,
    set_condition,
)
from lib_opendefence_core.models.v1alpha1 import (
    BindingObservation,
    ObjectRef,
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
        self.seen_credentials: list[tuple[PublicCredential, ...]] = []
        self.seen_roles: list[str | None] = []
        self.seen_groups: list[tuple[ResolvedRef, ...]] = []

    def reconcile(
        self,
        user: User,
        projection: UserProjection,
        revision: str,
    ) -> ProjectionReceipt:
        self.seen_previous.append(projection.previous)
        self.seen_credentials.append(projection.credentials)
        self.seen_roles.append(projection.tak_role)
        self.seen_groups.append(projection.groups)
        if self.failure:
            raise RuntimeError("fixture partial write")
        if self.mutate is not None:
            self.mutate.spec.callsign = "changed"
        return self.receipt or ProjectionReceipt(
            revision, "strict-v1", "strict-v1", "strict-v1", datetime.now(UTC) + timedelta(minutes=5)
        )


def reconciler(projector: Projector) -> tuple[BindingReconciler, KubernetesFixture, User]:
    fixture = KubernetesFixture()
    user = core_user()
    fixture.put(user, "users")
    return (
        BindingReconciler(
            fixture.sync_client(User, "users"),
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
    binding = worker.reconcile(user)
    assert condition(binding).status == "False"
    assert condition(binding).reason == "AuthorityUnavailable"
    assert binding.spec.user_ref.name == user.name
    assert binding.metadata and binding.metadata.owner_references and user.metadata
    assert binding.metadata.owner_references[0].uid == user.metadata.uid
    writes = len(fixture.writes)
    worker.reconcile(user)
    assert len(fixture.writes) == writes


def test_jni_projector_uses_user_permissions_and_retries_native_failures() -> None:
    runtime = MagicMock()
    worker, fixture, user = reconciler(JniProjector(runtime))
    assert user.status is not None
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    user.status.groups = [ResolvedRef(name="team", uid="group-uid")]
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).reason == "EnforcementUnverified"
    initial = runtime.reconcile_user.call_args
    assert initial.args[0] == "original-user"
    assert initial.args[2:] == ("ROLE_ADMIN", ("team",))
    user.spec.callsign = "second"
    fixture.put(user, "users")
    worker.reconcile(user)
    assert runtime.reconcile_user.call_args == initial
    runtime.reconcile_user.side_effect = Exception("Java transport failed")
    worker.run_once()
    binding = worker.bindings.get(binding_name(user), "tak")
    assert condition(binding).reason == "ProjectionFailed"


def test_projected_roles_drive_tak_roles_without_core_operator() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    now = datetime.now(UTC)
    user.spec.role_refs = [ObjectRef(name="superadmin")]
    assert projected_tak_role(user, now) == "ROLE_READONLY"
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "True"
    assert projector.seen_roles[-1] == "ROLE_READONLY"

    assert user.status is not None
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "True"
    assert projector.seen_roles[-1] == "ROLE_ADMIN"
    assert projector.seen_credentials[-1][0].fingerprint_sha256 == "a" * 64
    assert projector.seen_credentials[-1][0].serial_hex == "1"

    assert user.metadata is not None and user.metadata.annotations is not None
    accepted = user.metadata.annotations.pop(ACCEPTED_CREDENTIALS_ANNOTATION)
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "False"
    assert projector.seen_previous[-1][0].fingerprint_sha256 == "a" * 64
    assert projector.seen_credentials[-1] == ()
    assert projector.seen_roles[-1] == "ROLE_ADMIN"

    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = accepted
    user.status.roles = []
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "True"
    assert projector.seen_roles[-1] == "ROLE_READONLY"

    assert user.metadata is not None
    user.metadata.generation = 2
    with pytest.raises(ProjectionUnavailable):
        projected_tak_role(user, now)
    assert condition(worker.reconcile(user)).status == "False"
    assert projector.seen_roles[-1] is None
    assert projector.seen_credentials[-1] == ()

    user.spec.revoked_at = now
    assert projected_tak_role(user, now) is None
    assert condition(worker.reconcile(user)).status == "False"
    assert projector.seen_credentials[-1] == ()
    assert projector.seen_roles[-1] is None


def test_certificate_rollover_preserves_one_user_binding_and_role() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    assert user.status is not None and user.metadata is not None and user.metadata.annotations is not None
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    fixture.put(user, "users")
    original = worker.reconcile(user)
    accepted = json.loads(user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION])
    replacement = accepted["credentials"][0] | {"fingerprintSha256": "b" * 64, "serialHex": "2"}
    accepted["credentials"].append(replacement)
    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = json.dumps(accepted)
    fixture.put(user, "users")

    overlap = worker.reconcile(user)
    assert overlap.name == original.name
    assert condition(overlap).status == "True"
    assert {record.fingerprint_sha256 for record in projector.seen_credentials[-1]} == {"a" * 64, "b" * 64}
    assert projector.seen_roles[-1] == "ROLE_ADMIN"

    accepted["credentials"] = [replacement]
    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = json.dumps(accepted)
    fixture.put(user, "users")
    renewed = worker.reconcile(user)
    assert renewed.name == original.name
    assert condition(renewed).status == "True"
    assert {record.fingerprint_sha256 for record in projector.seen_previous[-1]} == {"a" * 64, "b" * 64}
    assert [record.fingerprint_sha256 for record in projector.seen_credentials[-1]] == ["b" * 64]
    assert projector.seen_roles[-1] == "ROLE_ADMIN"
    assert len([item for item in fixture.objects.values() if isinstance(item, UserBinding)]) == 1
    assert renewed.metadata is not None and renewed.metadata.annotations is not None
    applied = json.loads(renewed.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert [(item["fingerprintSha256"], item["serialHex"]) for item in applied["credentials"]] == [("b" * 64, "2")]


def test_full_readback_and_refresh() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    binding = worker.reconcile(user)
    assert condition(binding).status == "True"
    assert condition(binding).observed_generation == 1
    assert len(fixture.writes) == 5
    assert binding.metadata and binding.metadata.annotations
    assert binding.metadata.annotations["integration.opendefence.fi/applied-revision"] == "strict-v1"
    saved = json.loads(binding.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert saved["credentials"][0]["fingerprintSha256"] == "a" * 64
    projector.receipt = ProjectionReceipt(
        input_revision(user), "strict-v2", "strict-v2", "strict-v1", datetime.now(UTC) + timedelta(minutes=5)
    )
    assert condition(worker.reconcile(user)).status == "False"


@pytest.mark.parametrize("change", ["input", "api", "messaging", "expiry", "naive", "empty", "beyond-credential"])
def test_unverified_receipts_never_mark_ready(change: str) -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    receipt = ProjectionReceipt(input_revision(user), "rev", "rev", "rev", datetime.now(UTC) + timedelta(minutes=5))
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
    assert condition(worker.reconcile(user)).reason == "ProjectionUnverified"


def test_partial_failure_clears_synced() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    worker.reconcile(user)
    projector.failure = True
    with pytest.raises(RuntimeError):
        worker.reconcile(user)
    binding = next(resource for resource in fixture.objects.values() if isinstance(resource, UserBinding))
    assert condition(binding).reason == "ProjectionFailed"
    assert condition(binding).status == "False"


def test_user_changes_during_projection() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    stored = next(resource for resource in fixture.objects.values() if isinstance(resource, User))
    projector.mutate = stored
    assert condition(worker.reconcile(user)).reason == "InputsChanged"


def test_receipt_expires_during_core_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    tick = datetime.now(UTC)
    projector.receipt = ProjectionReceipt(input_revision(user), "rev", "rev", "rev", tick + timedelta(seconds=30))

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
    assert condition(worker.reconcile(user)).reason == "ProjectionUnverified"


def test_recreated_unapproved_user_gets_new_binding() -> None:
    worker, fixture, user = reconciler(UnavailableProjector())
    user.spec.approved_at = None
    fixture.put(user, "users")
    original = worker.reconcile(user)
    assert user.metadata is not None
    user.metadata.uid = "replacement-user"
    replacement = worker.reconcile(user)
    assert original.name != replacement.name
    assert len([item for item in fixture.objects.values() if isinstance(item, UserBinding)]) == 2


@pytest.mark.parametrize("change", ["label", "owner", "reference"])
def test_foreign_binding_is_preserved(change: str) -> None:
    worker, fixture, user = reconciler(UnavailableProjector())
    binding = worker.reconcile(user)
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
        worker.reconcile(user)
    assert len(fixture.writes) == writes


def test_input_revisions_ignore_binding_feedback_and_track_user_projection() -> None:
    user = core_user()
    observation = BindingObservation(name="binding", namespace="tak", uid="binding-uid", synced=False)
    user.status = UserStatus(publicKey="current", bindings=[observation], observedGeneration=1)
    original = input_revision(user)
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
    assert input_revision(user) == original
    assert user.metadata is not None and user.metadata.annotations is not None
    user.metadata.annotations[ACCEPTED_CREDENTIALS_ANNOTATION] = user.metadata.annotations[
        ACCEPTED_CREDENTIALS_ANNOTATION
    ].replace('"serialHex": "1"', '"serialHex": "2"')
    assert input_revision(user) != original
    original = input_revision(user)
    user.status.public_key = "changed"
    assert input_revision(user) != original
    revision = input_revision(user)
    user.status.groups = [ResolvedRef(name="group", uid="group-uid")]
    assert input_revision(user) != revision
    revision = input_revision(user)
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    assert input_revision(user) != revision


def test_only_projected_user_roles_and_groups_control_account_access() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    user.spec.role_refs = [ObjectRef(name="superadmin")]
    user.spec.group_refs = [ObjectRef(name="unresolved")]
    assert user.status is not None
    user.status.groups = [ResolvedRef(name="projected", uid="group-uid")]
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "True"
    assert projector.seen_roles[-1] == "ROLE_READONLY"
    assert projector.seen_groups[-1] == tuple(user.status.groups)

    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "True"
    assert projector.seen_roles[-1] == "ROLE_ADMIN"
    assert projector.seen_groups[-1] == tuple(user.status.groups)
    assert len(projector.seen_credentials[-1]) == 1

    user.status.roles = []
    user.status.groups = []
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "True"
    assert projector.seen_roles[-1] == "ROLE_READONLY"
    assert projector.seen_groups[-1] == ()
    assert len(projector.seen_credentials[-1]) == 1


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
        input_revision(user)


@pytest.mark.parametrize("raw", [None, "", "{}", '{"version":1,"credentials":[]}', "not-json"])
def test_missing_or_malformed_credential_metadata_keeps_binding_unready(raw: str | None) -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    assert user.metadata is not None
    user.metadata.annotations = {ACCEPTED_CREDENTIALS_ANNOTATION: raw} if raw is not None else {}
    assert condition(worker.reconcile(user)).reason == "CredentialsUnavailable"
    assert projector.seen_credentials == [()]


def test_removed_credentials_reach_projector_before_binding_stays_unready() -> None:
    projector = FixtureProjector()
    worker, _, user = reconciler(projector)
    assert condition(worker.reconcile(user)).status == "True"
    assert user.metadata is not None
    user.metadata.annotations = {}
    revision = input_revision(user)
    projector.receipt = ProjectionReceipt(
        revision, "strict-v2", "strict-v2", "old", datetime.now(UTC) + timedelta(minutes=5)
    )
    assert condition(worker.reconcile(user)).reason == "ProjectionUnverified"
    binding = worker.bindings.get(binding_name(user), "tak")
    assert binding.metadata and binding.metadata.annotations
    saved = json.loads(binding.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert saved["credentials"][0]["fingerprintSha256"] == "a" * 64
    projector.receipt = None
    assert condition(worker.reconcile(user)).status == "False"
    assert projector.seen_previous[-1] == projector.seen_credentials[0]
    assert projector.seen_credentials[-1] == ()
    binding = worker.bindings.get(binding_name(user), "tak")
    assert binding.metadata and binding.metadata.annotations
    saved = json.loads(binding.metadata.annotations["integration.opendefence.fi/applied-credentials"])
    assert saved["credentials"] == []


def test_applied_credentials_survive_reconciler_restart() -> None:
    first = FixtureProjector()
    worker, _, user = reconciler(first)
    worker.reconcile(user)
    restarted = BindingReconciler(worker.users, worker.bindings, FixtureProjector())
    assert user.metadata is not None
    user.metadata.annotations = {}
    assert condition(restarted.reconcile(user)).reason == "CredentialsUnavailable"
    assert isinstance(restarted.projector, FixtureProjector)
    assert restarted.projector.seen_previous[-1] == first.seen_credentials[0]


def test_invalid_applied_state_recovers_from_verified_projection() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    worker.reconcile(user)
    binding = next(resource for resource in fixture.objects.values() if isinstance(resource, UserBinding))
    assert binding.metadata and binding.metadata.annotations
    binding.metadata.annotations["integration.opendefence.fi/applied-credentials"] = "broken"
    fixture.put(binding, "userbindings")
    worker.projector = UnavailableProjector()
    assert condition(worker.reconcile(user)).reason == "AuthorityUnavailable"
    assert binding.metadata.annotations["integration.opendefence.fi/applied-credentials"] == "broken"
    worker.projector = projector
    assert condition(worker.reconcile(user)).reason == "ProjectionVerified"
    assert projector.seen_previous[-1] == ()
    updated = worker.bindings.get(binding_name(user), "tak")
    assert updated.metadata and updated.metadata.annotations
    assert updated.metadata.annotations["integration.opendefence.fi/applied-credentials"] != "broken"


def test_pending_user_has_no_credential_access() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    user.spec.approved_at = None
    assert user.status is not None
    user.status.roles = [ResolvedRef(name="superadmin", uid="role-uid")]
    user.status.groups = [ResolvedRef(name="projected", uid="group-uid")]
    fixture.put(user, "users")
    assert condition(worker.reconcile(user)).status == "False"
    assert projector.seen_credentials[-1] == ()
    assert projector.seen_roles[-1] is None
    assert projector.seen_groups[-1] == ()


def test_revoked_user_and_binding_remain_after_credential_removal() -> None:
    projector = FixtureProjector()
    worker, fixture, user = reconciler(projector)
    original = worker.reconcile(user)
    assert condition(original).status == "True"
    assert user.metadata is not None
    user.spec.revoked_at = datetime.now(UTC)
    fixture.put(user, "users")

    revoked = worker.reconcile(user)
    assert revoked.name == original.name
    assert condition(revoked).status == "False"
    assert projector.seen_previous[-1][0].fingerprint_sha256 == "a" * 64
    assert projector.seen_credentials[-1] == ()
    assert revoked.metadata is not None and revoked.metadata.annotations is not None
    assert (
        json.loads(revoked.metadata.annotations["integration.opendefence.fi/applied-credentials"])["credentials"] == []
    )
    retained = worker.users.get(user.name or "")
    assert retained.metadata is not None and retained.metadata.uid == user.metadata.uid
    assert retained.spec.revoked_at == user.spec.revoked_at
    assert len([item for item in fixture.objects.values() if isinstance(item, UserBinding)]) == 1
