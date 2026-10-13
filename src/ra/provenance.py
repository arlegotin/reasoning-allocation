"""Canonical identities and persistent exact/structured split ownership."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from ra.types import CoverInstance

SPLITS = ('discovery', 'train', 'validation', 'confirmatory', 'shift')


def _validate_ownership_entry(key: str, split: str) -> None:
    """Use identical namespace rules before registration, saving and loading."""
    if not isinstance(key, str) or ':' not in key or split not in SPLITS:
        raise ValueError('invalid split ownership entries')
    kind, identity = key.split(':', 1)
    if (kind not in ('template', 'content', 'instance') or not identity or
            (kind != 'template' and (len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity)))):
        raise ValueError('invalid split ownership entries')


def _hash(payload: object) -> str:
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('provenance must contain finite JSON primitives') from exc
    return hashlib.sha256(raw.encode()).hexdigest()


def derive_seed(master: str, split: str, template_index: int) -> int:
    if split not in SPLITS or not isinstance(master, str) or not master or type(template_index) is not int or template_index < 0:
        raise ValueError('seed requires master string, supported split and nonnegative template index')
    return int(_hash(['sha256-json-v1', master, split, template_index]), 16)


def instance_hash(instance: CoverInstance) -> str:
    from ra.exact import canonical_cover
    return _hash({'cover': canonical_cover(instance), 'lineage': instance.lineage})


def derive_cover(instance: CoverInstance, *, row_order=None, column_order=None, cost_scale: int = 1) -> CoverInstance:
    from ra.exact import canonical_cover
    canonical_cover(instance)
    m, n = instance.incidence.shape
    row_order = tuple(range(m)) if row_order is None else tuple(row_order)
    column_order = tuple(range(n)) if column_order is None else tuple(column_order)
    if (any(type(i) is not int for i in (*row_order, *column_order)) or sorted(row_order) != list(range(m)) or
            sorted(column_order) != list(range(n)) or type(cost_scale) is not int or cost_scale <= 0):
        raise ValueError('derivative requires permutations and a positive integer cost scale')
    a = instance.incidence[list(row_order), :][:, list(column_order)].tocsr()
    a.sort_indices()
    for array in (a.data, a.indices, a.indptr):
        array.flags.writeable = False
    lineage = {**instance.lineage, 'root_template_id': instance.lineage.get('root_template_id', instance.template_id),
               'ancestor_template_ids': sorted(set(instance.lineage.get('ancestor_template_ids', [])) | {instance.template_id}),
               'derivative': {'parent_instance_hash': instance_hash(instance), 'row_order': list(row_order),
                              'column_order': list(column_order), 'cost_scale': cost_scale}}
    derivative = replace(instance, instance_id='', incidence=a, costs=tuple(int(instance.costs[j]) * cost_scale for j in column_order), lineage=lineage)
    return replace(derivative, instance_id=instance_hash(derivative))


class SplitOwnership:
    """All declared template ancestors and exact contents have one split owner.

    No graph-isomorphism claim is made: permutations/scalings must retain their
    declared lineage. Register whole batches before persisting their artifacts.
    """
    def __init__(self):
        self.owners: dict[str, str] = {}

    def register(self, instance: CoverInstance, split: str) -> None:
        from ra.exact import canonical_cover
        if split not in SPLITS:
            raise ValueError('unsupported split')
        lineage = instance.lineage
        if not isinstance(lineage, dict):
            raise ValueError('lineage must be a primitive object')
        _hash(lineage)
        root = lineage.get('root_template_id', instance.template_id)
        ancestors = lineage.get('ancestor_template_ids', [])
        if not isinstance(ancestors, list):
            raise ValueError('ancestor_template_ids must be a list')
        templates = [instance.template_id, root, *ancestors]
        if any(not isinstance(t, str) or not t for t in templates):
            raise ValueError('template identities must be nonempty strings')
        identities = {'template:' + t for t in templates} | {'content:' + _hash(canonical_cover(instance))}
        derivative = lineage.get('derivative')
        if derivative is not None:
            if not isinstance(derivative, dict) or not isinstance(derivative.get('parent_instance_hash'), str):
                raise ValueError('derivative must declare its parent instance hash')
            identities.add('instance:' + derivative['parent_instance_hash'])
        identities.add('instance:' + instance_hash(instance))
        for key in identities:
            _validate_ownership_entry(key, split)
        if any(key in self.owners and self.owners[key] != split for key in identities):
            raise ValueError('exact or structured derivative crosses split ownership')
        self.owners.update({key: split for key in identities})

    def save(self, path: Path) -> None:
        for key, split in self.owners.items():
            _validate_ownership_entry(key, split)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_text(json.dumps({'schema_version': 1, 'owners': self.owners}, sort_keys=True, indent=2) + '\n')
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> SplitOwnership:
        from ra.config import ConfigError, _object, _nonfinite
        try:
            payload = json.loads(Path(path).read_text(), object_pairs_hook=_object, parse_constant=_nonfinite)
        except (json.JSONDecodeError, ConfigError) as exc:
            raise ValueError('invalid split ownership registry') from exc
        if not isinstance(payload, dict) or set(payload) != {'schema_version', 'owners'} or type(payload['schema_version']) is not int or payload['schema_version'] != 1 or not isinstance(payload['owners'], dict):
            raise ValueError('invalid split ownership registry schema')
        for key, split in payload['owners'].items():
            _validate_ownership_entry(key, split)
        owner = cls()
        owner.owners = payload['owners']
        return owner
