"""Immutable primitive records at the allocator/native boundary."""
from dataclasses import dataclass, field
from typing import Any
from enum import StrEnum
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class CoverInstance:
    instance_id: str
    template_id: str
    cell_id: str
    incidence: Any  # Original CSR; no numerical import during primitive initialization.
    costs: tuple[int, ...]
    lineage: dict[str, object]


@dataclass(frozen=True, slots=True)
class VerifiedAssignment:
    binary: tuple[int, ...]
    objective: int
    content_hash: str


@dataclass(frozen=True, order=True, slots=True)
class NodeKey:
    epoch: int
    number: int


@dataclass(frozen=True, slots=True)
class NodeRecord:
    key: NodeKey
    parent: NodeKey | None
    depth: int
    native_lower_bound: float
    native_estimate: float
    first_seen_selection: int
    ancestry_digest: str
    category: str


@dataclass(frozen=True, slots=True)
class DecisionContext:
    request_id: str
    snapshot_ns: int
    deadline_ns: int
    utility_local: float
    primal_original: float
    dual_original: float
    lower_bound_transformed: float
    cutoff_transformed: float
    processed_nodes: int
    frontier_size: int
    feature_schema_hash: str


@dataclass(frozen=True, slots=True)
class Allocation:
    root: NodeKey
    node_limit: int
    gain_prediction: float
    seconds_prediction: float
    seconds_q90: float | None
    selection_probability: float | None
    policy_state_hash: str


@dataclass(frozen=True, slots=True)
class LeaseOutcome:
    root: NodeKey
    node_limit: int
    work: int
    entry_ns: int
    dispatch_ns: int | None
    end_ns: int
    end_reason: str
    natural_completion: bool
    censored: bool
    unused_units: int
    body_ns: int
    continuation_ns: int
    post_deadline_work: int


@dataclass(frozen=True, slots=True)
class SelectionBoundary:
    entry_ns: int
    snapshot_ns: int | None
    dispatch_ns: int | None
    end_ns: int | None
    kind: str
    origin: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProgressRecord:
    request_id: str
    sequence: int
    child_ns: int
    receipt_ns: int | None
    primal_original: int | None
    dual_original: float
    incumbent_hash: str | None
    assignment_available: bool
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class AvailableProgress:
    assignment_available: bool
    utility: float
    primal_original: int | None
    dual_original: float
    incumbent_hash: str | None
    sequence: int | None = None


class AttemptStatus(StrEnum):
    COMPLETE = 'complete'
    DEADLINE = 'deadline'
    STARTUP_TIMEOUT = 'startup_timeout'
    OOM = 'oom'
    EXTERNAL_INTERRUPT = 'external_interrupt'
    NUMERICAL_ALARM = 'numerical_alarm'
    IMPLEMENTATION_ERROR = 'implementation_error'


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    instance_path: str
    instance_sha256: str
    instance_hash: str
    config_hash: str
    code_hash: str
    environment_hash: str
    method: str
    phase: str
    solver_seed: int
    budget_ns: int
    watchdog_grace_ns: int
    p0: int
    threads: int = 1
    integrality_tolerance: float = 1e-6
    bound_tolerance: float = 1e-6
    model_path: str | None = None
    model_hash: str | None = None
    build_hash: str | None = None
    prior_attempt_ids: tuple[str, ...] = ()
    prior_costs: dict[str, object] = field(default_factory=dict)
    launch_ns: int | None = None
    deadline_ns: int | None = None
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class Attempt:
    request_id: str
    status: str
    available: AvailableProgress
    clock_aligned: bool
    timestamps: dict[str, int | None]
    resources: dict[str, object]
    overshoot_ns: int
    duration_censored: bool
    error: str | None
    request: Request
    schema_version: int = 1
    attempt_id: str = field(default_factory=lambda: uuid4().hex)
    prior_attempt_id: str | None = None
    cumulative_prior_costs: dict[str, object] = field(default_factory=dict)
    quarantined: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'status', AttemptStatus(self.status))
        if self.request_id != self.request.request_id:
            raise ValueError('attempt/request identity mismatch')
        if not self.attempt_id or any(c not in '0123456789abcdef' for c in self.attempt_id) or len(self.attempt_id) != 32:
            raise ValueError('invalid attempt ID')
