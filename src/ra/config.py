"""Strict schemas for original workload inputs and serial public controls."""
from __future__ import annotations

from dataclasses import fields
from functools import lru_cache
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
    if kind == 'run':
        validate_run_config(config)
        return config
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
            ratios = config['row_column_ratios']
            if (not isinstance(ratios, list) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in ratios)):
                raise ConfigError('row_column_ratios must contain finite nonboolean numbers')
            if config['row_column_ratios'] != [.5, 1, 2] or config['degrees'] != [4, 8, 16] or config['block_counts'] != [2, 4, 8]:
                raise ConfigError('discovery requires the declared ratio, degree and block grid')
            validate_cell(GeneratorCell('redundant', 64, 32, 4, clone_fraction=config['clone_fraction'], bridge_multiplier=config['bridge_multiplier']))
            if not config_cells(config):
                raise ConfigError('empty valid probe grid')
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(str(exc)) from exc


def native_parameter_support() -> dict[str, dict[str, object]]:
    """Return independent metadata; harvest once per process/linked build.

    Each cold worker still pays its first installed-build harvest. Repeated
    request validation never repeats that immutable read or shares mutable maps.
    """
    from copy import deepcopy
    return deepcopy(_installed_native_parameter_support())


@lru_cache(maxsize=1)
def _installed_native_parameter_support() -> dict[str, dict[str, object]]:
    """Read names, types and ranges from this linked build's commented dump.

    Nothing here comes from remembered/web defaults. No solving is performed.
    A null minimum/maximum denotes an unbounded endpoint in standard JSON.
    """
    import re
    import tempfile
    from pyscipopt import Model
    model = Model()
    model.hideOutput()
    try:
        with tempfile.TemporaryDirectory(prefix='ra-native-') as directory:
            path = Path(directory)/'params.set'
            model.writeParams(str(path), comments=True, onlychanged=False, verbose=False)
            dump = path.read_text()
        result = {}
        pattern = r'# \[type: (\w+), advanced: \w+, range: \[([^,]+),([^\]]+)\], default: ([^\]]+)\]\n(nodeselection/[^\s]+) = ([^\n]+)'
        params = model.getParams()
        for typ, low, high, default, name, value in re.findall(pattern, dump):
            result[name] = {'type': typ, 'minimum': float(low) if math.isfinite(float(low)) else None,
                            'maximum': float(high) if math.isfinite(float(high)) else None, 'default': params[name]}
        choice_pattern = r'# \[type: (bool|char), advanced: \w+, range: \{([^}]+)\}, default: [^\]]+\]\n(nodeselection/[^\s]+) = [^\n]+'
        for typ, choices, name in re.findall(choice_pattern, dump):
            result[name] = {'type':typ,'choices': [False,True] if typ=='bool' else list(choices), 'default':params[name]}
        if not result:
            raise ConfigError('installed native parameter metadata unavailable')
        return result
    finally:
        model.freeProb()


def resolve_native_overrides(params: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    """Return an independent full parameter map; only allocation tuning is allowed."""
    if not isinstance(params, dict) or not isinstance(overrides, dict):
        raise ConfigError('parameter maps required')
    support = native_parameter_support() if overrides else {}
    result = dict(params)
    for name, value in overrides.items():
        if name not in params or name not in support:
            raise ConfigError(f'unsupported native allocation parameter: {name}')
        meta = support[name]
        if meta['type'] in ('bool','char'):
            if type(value) is not (bool if meta['type']=='bool' else str) or value not in meta['choices']:
                raise ConfigError(f'invalid installed type/choices: {name}')
            result[name] = value
            continue
        valid_type = type(value) is int if meta['type'] in ('int','longint') else type(value) in (int,float)
        if (not valid_type
                or meta['minimum'] is not None and value < meta['minimum']
                or meta['maximum'] is not None and value > meta['maximum']
                or abs(value) > 1.7976931348623157e308 or not math.isfinite(value)):
            raise ConfigError(f'invalid installed type/range: {name}')
        result[name] = value
    return result


def validate_run_config(config: dict[str, object]) -> None:
    from ra.allocators import make_allocator
    required = {'schema_version','purpose','input_manifests','methods','solver_seeds','run_order_seed','budgets_ns',
                'watchdog_grace_ns','lease_lengths','threads','integrality_tolerance','bound_tolerance'}
    if not isinstance(config,dict) or set(config) != required or type(config['schema_version']) is not int or config['schema_version'] != 1 or config['purpose'] != 'exploratory':
        raise ConfigError('unsupported run schema/fields/purpose')
    if config['threads'] != 1 or type(config['threads']) is not int:
        raise ConfigError('timed runs require one worker and one thread')
    for name in ('solver_seeds','budgets_ns','lease_lengths'):
        values = config[name]
        low = 0 if name == 'solver_seeds' else 1
        if not isinstance(values,list) or not values or any(type(v) is not int or v < low for v in values) or len(set(values)) != len(values):
            raise ConfigError(f'invalid {name}')
    if any(v>2147483647 for v in config['solver_seeds']): raise ConfigError('SCIP seed outside range')
    for name in ('run_order_seed','watchdog_grace_ns'):
        if type(config[name]) is not int or config[name] < (1 if name == 'watchdog_grace_ns' else 0): raise ConfigError(f'invalid {name}')
    for name in ('integrality_tolerance','bound_tolerance'):
        value=config[name]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<.5: raise ConfigError(f'invalid {name}')
    if not isinstance(config['input_manifests'],list) or not config['input_manifests'] or any(not isinstance(p,str) or not p for p in config['input_manifests']): raise ConfigError('input manifest paths required')
    methods=config['methods']
    if not isinstance(methods,list) or not methods: raise ConfigError('methods required')
    names=set()
    for method in methods:
        if not isinstance(method,dict) or method.get('kind') not in ('native','shared') or not isinstance(method.get('name'),str) or not method['name'] or method['name'] in names: raise ConfigError('invalid/duplicate method')
        names.add(method['name'])
        if method['kind']=='native':
            if set(method)!={'name','kind','overrides'} or not isinstance(method['overrides'],dict): raise ConfigError('invalid native method')
            from pyscipopt import Model
            model=Model(); model.hideOutput()
            try: resolve_native_overrides(model.getParams(),method['overrides'])
            finally: model.freeProb()
        else:
            if set(method)!={'name','kind','allocator','pool_size'}: raise ConfigError('invalid shared method')
            k=method['pool_size']
            if k is not None and (type(k) is not int or k<=0): raise ConfigError('invalid candidate pool size')
            make_allocator(method['allocator'],0)
            lengths=method['allocator'].get('bin_lengths',[method['allocator'].get('length',1)])
            if any(n not in config['lease_lengths'] for n in lengths): raise ConfigError('method length outside configured support')
