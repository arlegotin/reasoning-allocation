"""Immutable primitive records at the allocator/native boundary."""
from dataclasses import dataclass


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
