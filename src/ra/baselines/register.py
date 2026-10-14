"""Hash-addressed baseline cards and claim gates, without optional ML imports."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Sequence

from ra.config import ConfigError, _object, _nonfinite

STATUSES = {'reproduced', 'adapted', 'approximation', 'blocked', 'reference_only'}
REQUIRED_CONTROLS = frozenset(f'B{i}' for i in range(7))
NAMED_METHODS = frozenset(('labassi', 'mattick-mutschler', 'trgnn', 'deepbound', 'treecl'))
GATES = frozenset(('cpu_inference', 'cpu_backward', 'serialization', 'operators', 'live_features',
                   'hybrid_handoff', 'tiny_optimum', 'original_reproduction', 'cpu_resources'))


def _require(condition, message):
    if not condition:
        raise ConfigError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(values, *, nonempty=False):
    return isinstance(values, list) and (not nonempty or bool(values)) and all(_text(v) for v in values)


def configuration_digest(value: object) -> str:
    """Canonical JSON hash for the selected control object (not its whole file)."""
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ConfigError('configuration must be finite JSON') from exc
    return hashlib.sha256(raw).hexdigest()


def evidence_path(ref: object) -> Path:
    _require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'hash-addressed evidence required')
    _require(_text(ref['path']) and isinstance(ref['sha256'], str)
             and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'invalid evidence path/hash')
    path = Path(ref['path'])
    _require(not path.is_absolute() and '..' not in path.parts, 'evidence must use repository-relative paths')
    _require(path.resolve().is_relative_to(Path.cwd().resolve()), 'evidence escapes repository')
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f'evidence unavailable: {path}') from exc
    _require(hashlib.sha256(raw).hexdigest() == ref['sha256'], f'evidence hash mismatch: {path}')
    return path


def _evidence(refs, *, nonempty=False):
    _require(isinstance(refs, list) and (not nonempty or bool(refs)), 'evidence list required')
    for ref in refs:
        evidence_path(ref)


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(), object_pairs_hook=_object, parse_constant=_nonfinite)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f'invalid JSON evidence: {path}') from exc
    _require(isinstance(value, dict), f'JSON object required: {path}')
    return value


@dataclass(frozen=True, slots=True)
class BaselineCard:
    schema_version: int
    id: str
    method: str
    status: str
    source: dict[str, object]
    permissions: dict[str, object]
    original_regime: dict[str, object]
    changes: list[str]
    adapted_from: str | None
    configuration: dict[str, object] | None
    entry_point: dict[str, object] | None
    gates: dict[str, object]
    resources: dict[str, object]
    blockers: list[str]
    evidence: list[dict[str, object]]

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> BaselineCard:
        _require(isinstance(value, dict) and set(value) == set(cls.__dataclass_fields__), 'invalid BaselineCard fields')
        return cls(**deepcopy(value))

    def validate(self) -> None:
        _require(type(self.schema_version) is int and self.schema_version == 1, 'unsupported card schema')
        _require(_text(self.id) and re.fullmatch('[a-z0-9][a-z0-9-]*', self.id)
                 and _text(self.method) and _text(self.status) and self.status in STATUSES, 'invalid card identity/status')
        source_keys = {'paper_url', 'paper_revision', 'repository_url', 'commit', 'software_license', 'paper_license', 'inspected'}
        _require(isinstance(self.source, dict) and set(self.source) == source_keys, 'invalid source fields')
        _require(_text(self.source['paper_url']) and self.source['paper_url'].startswith('https://')
                 and _text(self.source['paper_revision']) and _text(self.source['paper_license'])
                 and _strings(self.source['inspected'], nonempty=True), 'paper pin and inspected source locations required')
        for name in ('repository_url', 'software_license'):
            _require(self.source[name] is None or _text(self.source[name]), f'invalid source {name}')
        commit = self.source['commit']
        _require(commit is None or isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit), 'invalid source commit')
        _require(isinstance(self.permissions, dict) and set(self.permissions) == {'code', 'checkpoints', 'teacher_assets', 'dependencies'},
                 'separate code/checkpoint/teacher/dependency terms required')
        for component, term in self.permissions.items():
            _require(isinstance(term, dict) and set(term) == {'status', 'terms', 'evidence'}
                     and _text(term['status']) and term['status'] in {'granted', 'unresolved', 'restricted', 'not_used'} and _text(term['terms']),
                     f'invalid permission: {component}')
            _evidence(term['evidence'], nonempty=True)
        regime_keys = {'architecture', 'loss', 'depth_weighting', 'teacher', 'candidate_comparison', 'hybrid_handoff', 'solver', 'hardware'}
        _require(isinstance(self.original_regime, dict) and set(self.original_regime) == regime_keys
                 and all(_text(v) for v in self.original_regime.values()), 'original regime and handoff required')
        _require(_strings(self.changes) and _strings(self.blockers), 'changes/blockers must be explicit lists')
        _evidence(self.evidence, nonempty=True)
        if self.configuration is not None:
            _require(isinstance(self.configuration, dict) and set(self.configuration) == {'id', 'path', 'sha256'}
                     and _text(self.configuration['id']), 'configuration ID and pin required')
            evidence_path({k: v for k, v in self.configuration.items() if k != 'id'})
        if self.entry_point is not None:
            evidence_path(self.entry_point)
        _require(isinstance(self.gates, dict) and set(self.gates) == GATES, 'all CPU/fidelity gates required')
        for name, gate in self.gates.items():
            _require(isinstance(gate, dict) and set(gate) == {'state', 'reason', 'evidence'}
                     and _text(gate['state']) and gate['state'] in {'passed', 'blocked', 'not_run'} and _text(gate['reason']), f'invalid gate: {name}')
            _evidence(gate['evidence'], nonempty=gate['state'] != 'not_run')
            if gate['state'] == 'passed':
                _require(self.configuration is not None and commit is not None, 'passed gates need source/config pins')
                for ref in gate['evidence']:
                    payload = read_json(evidence_path(ref))
                    _require(payload.get('baseline_id') == self.id and payload.get('gate') == name
                             and payload.get('success') is True and payload.get('source_commit') == commit
                             and payload.get('config_sha256') == self.configuration['sha256'],
                             f'gate evidence does not bind baseline/source/config: {name}')
        _require(isinstance(self.resources, dict) and set(self.resources) == {'measured', 'costs', 'failed_attempts', 'notes'}
                 and type(self.resources['measured']) is bool and _text(self.resources['notes'])
                 and isinstance(self.resources['failed_attempts'], list), 'resource/failure accounting required')
        _evidence(self.resources['failed_attempts'])
        costs = self.resources['costs']
        if self.resources['measured']:
            _require(isinstance(costs, dict) and {'teacher_cpu_ns', 'training_cpu_ns', 'inference_cpu_ns', 'peak_rss_bytes'} <= costs.keys()
                     and all(type(v) is int and v >= 0 for v in costs.values()), 'measured CPU/teacher/training/inference/memory costs required')
        else:
            _require(costs is None, 'unmeasured costs must remain unknown')
        active = self.status in {'reproduced', 'adapted'}
        if active:
            _require(commit is not None and _text(self.source['repository_url']) and _text(self.source['software_license']),
                     'executable contender needs pinned source/software terms')
            _require(self.permissions['code']['status'] == 'granted'
                     and self.permissions['dependencies']['status'] == 'granted', 'author-code and dependency reuse must be granted separately')
            _require(all(self.permissions[k]['status'] in {'granted', 'not_used'} for k in ('checkpoints', 'teacher_assets')),
                     'checkpoint/teacher reuse must be permitted or explicitly unused')
            _require(self.configuration is not None and self.entry_point is not None, 'pinned configuration and executable entry point required')
            _require(all(g['state'] == 'passed' for g in self.gates.values()) and self.resources['measured']
                     and not self.blockers, 'unpassed fidelity/resource gate blocks reproduction')
        if self.status == 'adapted':
            _require(_text(self.adapted_from) and self.adapted_from != self.id and bool(self.changes), 'adaptation needs original ID and explicit changes')
        else:
            _require(self.adapted_from is None, 'only adaptations have an original ID')
        if self.status == 'blocked':
            _require(bool(self.blockers) and self.entry_point is None, 'blocked card needs specific blockers and no executable')
        if self.status == 'reference_only':
            _require(self.entry_point is None, 'reference-only card cannot expose executable')
        if self.status == 'approximation':
            _require('approximation' in self.method.lower() and bool(self.changes), 'paper-inspired approximation must be explicitly named')


def validate_register(register: dict[str, object], cards: Sequence[dict[str, object]]) -> None:
    _require(isinstance(register, dict), 'baseline register object required')
    # The shipped register extends Task13's full mandatory file without rewriting controls.
    if 'baseline_register' in register:
        section = register['baseline_register']
        _require(isinstance(section, dict), 'baseline_register object required')
        register = {**section, 'selected': register.get('selected')}
        refs = register.get('cards')
        _require(isinstance(refs, list) and bool(refs), 'locked literature cards required')
        locked = [read_card(ref) for ref in refs]
        _require(all(isinstance(c, dict) and _text(c.get('id')) for c in locked), 'invalid locked card identity')
        _require(NAMED_METHODS <= {c.get('id') for c in locked}, 'every required named method needs a disposition')
        _require(isinstance(cards, Sequence) and not isinstance(cards, (str, bytes))
                 and len(cards) == len(locked), 'locked literature cards cannot disappear')
        _require(all(isinstance(c, dict) and _text(c.get('id')) for c in cards), 'invalid supplied card identity')
        _require({c.get('id') for c in cards if isinstance(c, dict)} == {c.get('id') for c in locked},
                 'locked literature identities cannot disappear')
        _require(all(c in locked for c in cards), 'supplied cards must match locked hash-addressed records')
    _require(type(register.get('schema_version')) is int and register['schema_version'] == 1, 'unsupported register schema')
    selected, pins = register.get('selected'), register.get('control_pins')
    _require(isinstance(selected, dict) and isinstance(pins, dict) and REQUIRED_CONTROLS <= selected.keys()
             and REQUIRED_CONTROLS <= pins.keys(), 'required B0-B6 controls cannot disappear')
    for control, pin in pins.items():
        _require(control in selected and configuration_digest(selected[control]) == pin, f'control configuration drift: {control}')
    comparisons = register.get('comparison_ids')
    _require(_strings(comparisons) and len(comparisons) == len(set(comparisons))
             and REQUIRED_CONTROLS <= set(comparisons), 'required distinct control comparisons missing')
    _evidence(register.get('evidence'), nonempty=True)
    _require(isinstance(cards, Sequence) and not isinstance(cards, (str, bytes)), 'cards sequence required')
    parsed = [BaselineCard.from_dict(c) for c in cards]
    by_id = {c.id: c for c in parsed}
    _require(len(by_id) == len(parsed) and not set(by_id) & set(selected), 'duplicate baseline identity')
    _require(set(comparisons) <= set(selected) | set(by_id), 'unknown comparison baseline')
    for card in parsed:
        if card.status in {'reproduced', 'adapted'}:
            _require(card.id in comparisons, 'reproduced contenders cannot be excluded by performance')
        if card.id in comparisons:
            _require(card.status in {'reproduced', 'adapted', 'approximation'}, 'unavailable contender cannot enter comparisons')
        if card.status == 'adapted':
            original = by_id.get(card.adapted_from)
            _require(original is not None and original.status == 'reproduced', 'adaptation requires reproduced original record')
            _require(card.source['commit'] == original.source['commit'] and card.configuration['id'] != original.configuration['id']
                     and card.configuration['sha256'] != original.configuration['sha256'], 'adaptation requires its own source-matched configuration')
    claims = register.get('claims')
    _require(isinstance(claims, list), 'explicit claims list required')
    for claim in claims:
        _require(isinstance(claim, dict) and set(claim) == {'baseline_id', 'kind', 'evidence'}, 'invalid claim fields')
        _require(_text(claim['baseline_id']) and _text(claim['kind']), 'claim identity/kind must be strings')
        card = by_id.get(claim['baseline_id'])
        allowed = {'named_superiority': 'reproduced', 'adapted_superiority': 'adapted', 'approximation_comparison': 'approximation'}
        _require(card is not None and claim['kind'] in allowed and card.status == allowed[claim['kind']]
                 and card.id in comparisons, 'unavailable/approximate/adapted method cannot support unqualified named superiority')
        _evidence(claim['evidence'], nonempty=True)
        _require(card.configuration is not None, 'comparison claims need a pinned configuration')
        for ref in claim['evidence']:
            outcome = read_json(evidence_path(ref))
            _require(outcome.get('baseline_id') == card.id and outcome.get('kind') == claim['kind']
                     and outcome.get('source_commit') == card.source['commit']
                     and outcome.get('config_sha256') == card.configuration['sha256']
                     and outcome.get('comparison_complete') is True and _text(outcome.get('scope'))
                     and outcome.get('outcome') == 'candidate_superior',
                     'claim needs configuration-bound comparison outcome evidence, not access evidence')


def read_card(ref: object) -> dict[str, object]:
    text = evidence_path(ref).read_text()
    blocks = re.findall(r'^```json\n(.*?)\n```$', text, re.MULTILINE | re.DOTALL)
    _require(len(blocks) == 1, 'card needs exactly one JSON record')
    try:
        card = json.loads(blocks[0], object_pairs_hook=_object, parse_constant=_nonfinite)
    except json.JSONDecodeError as exc:
        raise ConfigError('invalid card JSON') from exc
    _require(isinstance(card, dict), 'card JSON object required')
    return card


def load_register(path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    register = read_json(path)
    section = register.get('baseline_register')
    _require(isinstance(section, dict) and isinstance(section.get('cards'), list) and section['cards'], 'registered literature cards required')
    cards = [read_card(ref) for ref in section['cards']]
    validate_register(register, cards)
    return register, cards


def reproduce_baseline(baseline: str, config_path: Path, out: Path, *, dry_run: bool = False) -> dict[str, object]:
    """Fail before output, imports, downloads or solves when no permitted port exists.

    No ports are installed in this bounded disposition stage. A future permitted
    port must add its real executable route and CPU/live/tiny fixtures together;
    editing a status or providing an arbitrary script cannot launch code here.
    """
    _, cards = load_register(config_path)
    card = next((c for c in cards if c['id'] == baseline), None)
    _require(card is not None, f'unknown literature baseline: {baseline}')
    if card['status'] not in {'reproduced', 'adapted'}:
        raise ConfigError(f"{baseline} is {card['status']}; reproduce unavailable: {'; '.join(card['blockers']) or 'no faithful permitted port'}")
    raise ConfigError(f'{baseline}: no permitted executable port installed; register metadata alone cannot launch reproduction')
