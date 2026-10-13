"""Strict JSON schemas for implemented workload generation only."""
from __future__ import annotations

from dataclasses import fields
import json
import math
from pathlib import Path


class ConfigError(ValueError):
    """A configuration is malformed or outside an implemented schema."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f'duplicate configuration key: {key}')
        result[key] = value
    return result


def _nonfinite(value):
    raise ConfigError(f'nonfinite JSON constant: {value}')


def load_config(path: Path, kind: str) -> dict[str, object]:
    try:
        config = json.loads(Path(path).read_text(), object_pairs_hook=_object, parse_constant=_nonfinite)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ConfigError(str(exc)) from exc
    if kind == 'generation':
        if not isinstance(config, dict):
            raise ConfigError('configuration must be a JSON object')
        kind = 'workload_probes' if config.get('purpose') == 'discovery' else 'workload'
    validate_config(config, kind)
    return config


def validate_config(config: dict[str, object], kind: str) -> None:
    from ra.data import FAMILIES, GeneratorCell, config_cells, validate_cell
    common = {'schema_version', 'purpose', 'master_seed', 'templates_per_cell'}
    if kind == 'workload':
        required, optional, purpose = common | {'cells'}, {'family_weights'}, 'workload'
    elif kind == 'workload_probes':
        required = common | {'column_counts', 'row_column_ratios', 'degrees', 'block_counts', 'clone_fraction', 'bridge_multiplier'}
        optional, purpose = set(), 'discovery'
    else:
        raise ConfigError(f'unsupported configuration kind: {kind}')
    if not isinstance(config, dict) or required - config.keys() or config.keys() - required - optional:
        raise ConfigError('missing or unknown configuration fields')
    if type(config['schema_version']) is not int or config['schema_version'] != 1 or config['purpose'] != purpose:
        raise ConfigError('unsupported schema version or purpose')
    if not isinstance(config['master_seed'], str) or not config['master_seed']:
        raise ConfigError('master_seed must be a nonempty string')
    if type(config['templates_per_cell']) is not int or config['templates_per_cell'] <= 0:
        raise ConfigError('templates_per_cell must be a positive integer')
    try:
        if kind == 'workload':
            if not isinstance(config['cells'], list) or not config['cells']:
                raise ConfigError('cells must be a nonempty list')
            allowed = {f.name for f in fields(GeneratorCell)}
            seen = set()
            for cell in config['cells']:
                if not isinstance(cell, dict) or cell.keys() - allowed:
                    raise ConfigError('unknown cell fields')
                built = GeneratorCell(**cell)
                validate_cell(built)
                signature = repr(built)
                if signature in seen:
                    raise ConfigError('duplicate generator cells')
                seen.add(signature)
            present = {c['family'] for c in config['cells']}
            weights = config.get('family_weights')
            if weights is not None:
                if not isinstance(weights, dict) or set(weights) != present:
                    raise ConfigError('family weights must specify exactly the present families')
                if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights.values()) or
                        not math.isfinite(sum(weights.values())) or sum(weights.values()) <= 0):
                    raise ConfigError('family weights must be finite nonnegative with positive sum')
        else:
            for key in ('column_counts', 'degrees', 'block_counts'):
                values = config[key]
                if not isinstance(values, list) or not values or any(type(v) is not int or v <= 0 for v in values) or len(set(values)) != len(values):
                    raise ConfigError(f'{key} must be distinct positive integer values')
            counts = config['column_counts']
            if counts[0] != 64 or any(b != 2 * a for a, b in zip(counts, counts[1:])):
                raise ConfigError('discovery column counts must start at 64 and double')
            if config['row_column_ratios'] != [.5, 1, 2] or config['degrees'] != [4, 8, 16] or config['block_counts'] != [2, 4, 8]:
                raise ConfigError('discovery requires the declared ratio, degree and block grid')
            validate_cell(GeneratorCell('redundant', 64, 32, 4, clone_fraction=config['clone_fraction'], bridge_multiplier=config['bridge_multiplier']))
            if not config_cells(config):
                raise ConfigError('empty valid probe grid')
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(str(exc)) from exc
