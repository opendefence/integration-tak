"""Serialized Core resource reconciliation, independent of HTTP delivery."""

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Protocol

from cloudcoil.apimachinery import ObjectMeta, OwnerReference, Time
from cloudcoil.client import APIClient
from cloudcoil.errors import APIError, ResourceConflict, ResourceNotFound
import httpx

from opendefence_integration_tak.cluster import cluster_config
from opendefence_integration_tak.certificates import (
    ACCEPTED_CREDENTIALS_ANNOTATION,
    PublicCredential,
    accepted_credential_records,
    public_credential_records,
)
from opendefence_integration_tak.tak_jni import TakJvmRuntime

from lib_opendefence_core.models.v1alpha1 import (
    API_VERSION,
    ObjectRef,
    User,
    UserBinding,
    UserBindingSpec,
    UserBindingStatus,
)
from lib_opendefence_core.models.v1alpha1.common import PlatformCondition, ResolvedRef

_LABEL = "app.kubernetes.io/managed-by"
_MANAGER = "opendefence-integration-tak"
_REVISION = "integration.opendefence.fi/input-revision"
_USER_UID = "integration.opendefence.fi/user-uid"
_APPLIED_REVISION = "integration.opendefence.fi/applied-revision"
_APPLIED_CREDENTIALS = "integration.opendefence.fi/applied-credentials"
_VALID_UNTIL = "integration.opendefence.fi/valid-until"
_LOGGER = logging.getLogger(__name__)


class ProjectionUnavailable(Exception):
    """No fresh Core policy or verified strict server capability."""


@dataclass(frozen=True, slots=True)
class ProjectionReceipt:
    input_revision: str
    desired_revision: str
    messaging_revision: str
    api_revision: str
    valid_until: datetime

    def current(self, revision: str, now: datetime) -> bool:
        return bool(self.desired_revision) and (
            self.input_revision == revision
            and self.desired_revision == self.messaging_revision == self.api_revision
            and self.valid_until.tzinfo is not None
            and self.valid_until > now
        )


@dataclass(frozen=True, slots=True)
class UserProjection:
    previous: tuple[PublicCredential, ...]
    credentials: tuple[PublicCredential, ...]
    tak_role: str | None
    groups: tuple[ResolvedRef, ...]


class Projector(Protocol):
    def reconcile(
        self,
        user: User,
        projection: UserProjection,
        revision: str,
    ) -> ProjectionReceipt | None:
        """Apply the full approved set and permissions; read back uncertain writes.

        Previous credentials include expired records and are only a retry hint.
        Read TAK state because the binding may predate this annotation or a write may be partial.
        An empty credential set removes access.
        Implementations own one JVM in this process and return Python values only.
        One User owns one UserBinding and separate TAK certificate identities.
        Derive each identity's role and groups only from the User projection.
        Bind credentials by exact fingerprint and issuer/serial pair.
        Remove only credentials absent from the accepted set before confirming readback.
        Keep the remaining certificate identities during rollover.
        A receipt requires verified messaging AND API enforcement. Never synthesize
        it from file-auth or scalar registerCert results.
        Return None when native records are applied but enforcement is unverified.
        """
        ...


class UnavailableProjector:
    def reconcile(
        self,
        user: User,
        projection: UserProjection,
        revision: str,
    ) -> ProjectionReceipt:
        raise ProjectionUnavailable


class JniProjector:
    def __init__(self, runtime: TakJvmRuntime) -> None:
        self.runtime = runtime

    def reconcile(self, user: User, projection: UserProjection, revision: str) -> None:
        if user.metadata is None or not user.metadata.uid:
            raise ValueError("Core User UID is missing")
        try:
            self.runtime.reconcile_user(
                user.metadata.uid,
                projection.credentials,
                projection.tak_role,
                tuple(group.name for group in projection.groups),
            )
        except Exception:
            raise RuntimeError("TAK User projection failed") from None
        # shortcut: JNI verifies native records; strict admission still needs both-JVM readback.


def input_revision(user: User) -> str:
    if user.metadata is None or not user.metadata.uid or not user.name:
        raise ValueError("Core User identity is missing")
    user_value: dict[str, object] = {
        "name": user.name,
        "uid": user.metadata.uid,
        "deletingAt": user.metadata.deletion_timestamp.model_dump(mode="json")
        if user.metadata.deletion_timestamp
        else None,
        "spec": user.spec.model_dump(mode="json", by_alias=True),
    }
    user_value["acceptedCredentials"] = (
        (user.metadata.annotations or {}).get(ACCEPTED_CREDENTIALS_ANNOTATION) if user.metadata else None
    )
    empty_status: dict[str, object] = {}
    user_value["status"] = (
        user.status.model_dump(mode="json", by_alias=True, exclude={"bindings", "conditions", "observed_generation"})
        if user.status
        else empty_status
    )
    return hashlib.sha256(json.dumps(user_value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def binding_name(user: User) -> str:
    if user.metadata is None or not user.metadata.uid:
        raise ValueError("Core User UID is missing")
    return "tak-" + hashlib.sha256(user.metadata.uid.encode()).hexdigest()[:32]


def _approved_user(user: User, now: datetime) -> bool:
    approved_at = user.spec.approved_at
    return (
        approved_at is not None
        and approved_at.tzinfo is not None
        and approved_at <= now
        and user.spec.revoked_at is None
    )


def accepted_user_credentials(user: User, now: datetime) -> tuple[PublicCredential, ...]:
    if not _approved_user(user, now):
        return ()
    try:
        return accepted_credential_records(
            (user.metadata.annotations or {}).get(ACCEPTED_CREDENTIALS_ANNOTATION) if user.metadata else None,
            now=now,
        )
    except ValueError:
        return ()


def projected_tak_role(user: User, now: datetime) -> str | None:
    if not _approved_user(user, now):
        return None
    if (
        user.metadata is None
        or user.metadata.generation is None
        or user.status is None
        or user.status.observed_generation != user.metadata.generation
    ):
        raise ProjectionUnavailable("User role projection is not current")
    return "ROLE_ADMIN" if any(role.name == "superadmin" for role in user.status.roles) else "ROLE_READONLY"


def _user_projection(
    user: User, previous: tuple[PublicCredential, ...], credentials: tuple[PublicCredential, ...], now: datetime
) -> UserProjection:
    try:
        role = projected_tak_role(user, now)
    except ProjectionUnavailable:
        return UserProjection(previous, (), None, ())
    groups = tuple(user.status.groups) if role is not None and user.status else ()
    return UserProjection(previous, credentials, role, groups)


def applied_credentials(binding: UserBinding) -> tuple[PublicCredential, ...]:
    raw = (binding.metadata.annotations or {}).get(_APPLIED_CREDENTIALS) if binding.metadata else None
    if raw is None:
        return ()
    try:
        return public_credential_records(raw)
    except ValueError:
        _LOGGER.warning("Invalid applied credential hint; reconcile from TAK state")
        return ()


def set_condition(binding: UserBinding, synced: bool, reason: str, now: datetime) -> bool:
    generation = binding.metadata.generation if binding.metadata else None
    status = binding.status or UserBindingStatus()
    current = next((item for item in status.conditions if item.type == "Synced"), None)
    desired = "True" if synced else "False"
    condition = PlatformCondition(
        type="Synced",
        status=desired,
        reason=reason,
        message=reason,
        lastTransitionTime=current.last_transition_time if current and current.status == desired else Time(now),
        observedGeneration=generation,
    )
    replacement = [item for item in status.conditions if item.type != "Synced"] + [condition]
    changed = replacement != status.conditions or status.observed_generation != generation
    status.conditions = replacement
    status.observed_generation = generation
    binding.status = status
    return changed


class BindingReconciler:
    def __init__(
        self,
        users: APIClient[User],
        bindings: APIClient[UserBinding],
        projector: Projector,
    ) -> None:
        self.users, self.bindings = users, bindings
        self.namespace, self.projector = bindings.default_namespace, projector

    def _binding(self, user: User) -> UserBinding:
        if user.metadata is None or not user.metadata.uid or not user.name:
            raise ValueError("Core User identity is missing")
        try:
            binding = self.bindings.get(binding_name(user), self.namespace)
        except ResourceNotFound:
            binding = self.bindings.create(
                UserBinding(
                    kind="UserBinding",
                    metadata=ObjectMeta(
                        name=binding_name(user),
                        namespace=self.namespace,
                        labels={_LABEL: _MANAGER},
                        owner_references=[
                            OwnerReference(
                                api_version=API_VERSION,
                                kind="User",
                                name=user.name,
                                uid=user.metadata.uid,
                                controller=True,
                            )
                        ],
                    ),
                    spec=UserBindingSpec(userRef=ObjectRef(name=user.name)),
                )
            )
        owners = binding.metadata.owner_references if binding.metadata else None
        if (
            binding.spec.user_ref.name != user.name
            or not owners
            or not any(
                owner.uid == user.metadata.uid
                and owner.kind == "User"
                and owner.api_version == user.api_version
                and owner.name == user.name
                for owner in owners
            )
            or not binding.metadata
            or (binding.metadata.labels or {}).get(_LABEL) != _MANAGER
        ):
            raise ValueError("Binding ownership conflict")
        return binding

    def _status(self, binding: UserBinding, synced: bool, reason: str) -> UserBinding:
        if set_condition(binding, synced, reason, datetime.now(UTC)):
            return self.bindings.update_status(binding)
        return binding

    def _record_applied(
        self, binding: UserBinding, receipt: ProjectionReceipt, credentials: tuple[PublicCredential, ...]
    ) -> UserBinding:
        if binding.metadata is None:
            raise ValueError("Binding metadata is missing")
        annotations = binding.metadata.annotations or {}
        records = json.dumps(
            {
                "version": 1,
                "credentials": [
                    {
                        "fingerprintSha256": record.fingerprint_sha256,
                        "serialHex": record.serial_hex,
                        "issuerId": record.issuer_id,
                        "notBefore": record.not_before.isoformat(),
                        "notAfter": record.not_after.isoformat(),
                    }
                    for record in credentials
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        applied = {
            _APPLIED_REVISION: receipt.desired_revision,
            _APPLIED_CREDENTIALS: records,
            _VALID_UNTIL: receipt.valid_until.isoformat(),
        }
        if any(annotations.get(key) != value for key, value in applied.items()):
            binding.metadata.annotations = annotations | applied
            return self.bindings.update(binding)
        return binding

    def reconcile(self, user: User) -> UserBinding:
        revision = input_revision(user)
        binding = self._binding(user)
        if binding.metadata is None or user.metadata is None:
            raise ValueError("Resource metadata is missing")
        annotations = binding.metadata.annotations or {}
        if annotations.get(_REVISION) != revision or annotations.get(_USER_UID) != user.metadata.uid:
            # Clear readiness first; annotation publication alone cannot make stale status current.
            binding = self._status(binding, False, "InputsChanged")
            if binding.metadata is None:
                raise ValueError("Binding metadata is missing")
            binding.metadata.annotations = annotations | {_REVISION: revision, _USER_UID: user.metadata.uid or ""}
            binding = self.bindings.update(binding)
        previous_credentials = applied_credentials(binding)
        credentials = accepted_user_credentials(user, datetime.now(UTC))
        try:
            projection = _user_projection(user, previous_credentials, credentials, datetime.now(UTC))
            receipt = self.projector.reconcile(user, projection, revision)
        except ProjectionUnavailable:
            return self._status(binding, False, "CredentialsUnavailable" if not credentials else "AuthorityUnavailable")
        except Exception:
            self._status(binding, False, "ProjectionFailed")
            raise
        if (
            receipt is None
            or not receipt.current(revision, datetime.now(UTC))
            or (
                projection.credentials
                and receipt.valid_until > min(record.not_after for record in projection.credentials)
            )
        ):
            return self._status(binding, False, "EnforcementUnverified" if receipt is None else "ProjectionUnverified")
        if not projection.credentials:
            return self._status(self._record_applied(binding, receipt, ()), False, "CredentialsUnavailable")
        if user.name is None:
            raise ValueError("Core User name is missing")
        try:
            fresh_user = self.users.get(user.name)
        except APIError, httpx.RequestError:
            self._status(binding, False, "AuthorityUnavailable")
            raise
        if input_revision(fresh_user) != revision:
            return self._status(binding, False, "InputsChanged")
        binding = self._record_applied(binding, receipt, projection.credentials)
        if not receipt.current(revision, datetime.now(UTC)):
            return self._status(binding, False, "ProjectionUnverified")
        return self._status(binding, True, "ProjectionVerified")

    def run_once(self) -> None:
        users = list(self.users.list())
        for user in users:
            try:
                self.reconcile(user)
            except ResourceConflict:
                _LOGGER.warning("Binding conflict; retry on next scan")
            except ValueError:
                _LOGGER.error("Invalid Core identity or binding ownership; skipped this user")
            except RuntimeError:
                _LOGGER.error("TAK projection failed; retry this User on the next scan")


def run_operator(namespace: str) -> None:
    """One JVM and one serial scan for the small installation.

    shortcut: poll every ten seconds; use informers if measured scale needs them.
    """
    tak = TakJvmRuntime()
    try:
        tak.start()
        with cluster_config(namespace=namespace) as config:
            reconciler = BindingReconciler(
                User.client(config),
                UserBinding.client(config, namespace=namespace),
                JniProjector(tak),
            )
            while True:
                try:
                    certificate = Path("/var/run/tak-admin/tls.crt")
                    if certificate.is_file():
                        tak.register_admin(certificate)
                    else:
                        tak.check()
                except Exception:
                    _LOGGER.error("TAK management unavailable; projection remains unready")
                try:
                    reconciler.run_once()
                except APIError, httpx.RequestError, ValueError:
                    _LOGGER.error("Core scan failed; no projection is marked ready")
                try:
                    tak.reconcile_connections()
                except Exception:
                    _LOGGER.error("TAK connection reconciliation failed; retry on the next scan")
                time.sleep(10)
    finally:
        tak.close()
