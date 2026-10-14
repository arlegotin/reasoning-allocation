"""Versioned deterministic weighted cover recipes; no solving or fitting."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random

from ra.types import CoverInstance

GENERATOR_VERSION = 'weighted-cover-v2-ordinary-clones'
FAMILIES = ('uniform', 'block', 'redundant')


class GenerationError(ValueError):
    """A seeded generation failed explicitly; callers must retain this seed."""
    def __init__(self, template_seed: int, clone_count: int, eligible_columns: tuple[int, ...]):
        self.template_seed = template_seed
        self.clone_count = clone_count
        self.eligible_columns = eligible_columns
        super().__init__(f'no eligible ordinary clone parent: template_seed={template_seed}, clone_count={clone_count}')


def _clone_count(cell: GeneratorCell) -> int:
    # The declared decimal fraction, rather than its binary-float product,
    # determines the mathematical floor (e.g. .58 * 50 gives 29).
    return math.floor(Fraction(str(cell.clone_fraction)) * cell.columns)


@dataclass(frozen=True, slots=True)
class GeneratorCell:
    family: str
    columns: int
    rows: int
    degree: int
    blocks: int | None = None
    cost_distribution: str = 'uniform'
    low_cost_probability: float | None = None
    clone_fraction: float = 0
    rare_row_proportion: float = .02
    bridge_multiplier: int = 1


def validate_cell(cell: GeneratorCell) -> None:
    if cell.family not in FAMILIES:
        raise ValueError('unknown cover family')
    if any(type(v) is not int or v <= 0 for v in (cell.columns, cell.rows, cell.degree)):
        raise ValueError('columns, rows, and degree must be positive integers')
    if (isinstance(cell.clone_fraction, bool) or not isinstance(cell.clone_fraction, (int, float)) or
            not math.isfinite(cell.clone_fraction) or not 0 <= cell.clone_fraction < 1):
        raise ValueError('clone fraction must be in [0, 1)')
    if (isinstance(cell.rare_row_proportion, bool) or not isinstance(cell.rare_row_proportion, (int, float)) or
            not math.isfinite(cell.rare_row_proportion) or not 0 <= cell.rare_row_proportion <= 1):
        raise ValueError('rare row proportion must be in [0, 1]')
    if type(cell.bridge_multiplier) is not int or cell.bridge_multiplier < 1:
        raise ValueError('bridge multiplier must be a positive integer')
    if cell.family != 'redundant' and (cell.clone_fraction != 0 or cell.bridge_multiplier != 1 or cell.rare_row_proportion != .02):
        raise ValueError('clone, rare row and bridge parameters apply only to redundant family')
    base_count = cell.columns - _clone_count(cell)
    if cell.degree > base_count:
        raise ValueError('degree exceeds distinct available base columns')
    if cell.family == 'block':
        if type(cell.blocks) is not int or not 2 <= cell.blocks <= cell.columns:
            raise ValueError('block count must be an integer between 2 and column count')
        sizes = [cell.columns // cell.blocks + (i < cell.columns % cell.blocks) for i in range(cell.blocks)]
        for size in sizes:
            inside = min((4 * cell.degree + 4) // 5, size)
            if cell.degree - inside > cell.columns - size:
                raise ValueError('outside sample exceeds available columns')
    elif cell.blocks is not None:
        raise ValueError('blocks apply only to block family')
    if cell.cost_distribution not in ('uniform', 'mixture'):
        raise ValueError('unknown cost distribution')
    if cell.cost_distribution == 'mixture':
        p = cell.low_cost_probability
        if (cell.family != 'block' or isinstance(p, bool) or not isinstance(p, (int, float)) or
                not math.isfinite(p) or not 0 <= p <= 1):
            raise ValueError('block cost mixture requires declared Bernoulli probability')
    elif cell.low_cost_probability is not None:
        raise ValueError('Bernoulli probability applies only to mixture costs')


def generate_cover(cell: GeneratorCell, template_seed: int) -> CoverInstance:
    validate_cell(cell)
    if type(template_seed) is not int or template_seed < 0:
        raise ValueError('template seed must be a nonnegative integer')
    from scipy.sparse import csr_matrix
    from ra.provenance import instance_hash
    rng = random.Random(template_seed)
    cell_payload = json.dumps(asdict(cell), sort_keys=True, separators=(',', ':'))
    cell_id = hashlib.sha256(cell_payload.encode()).hexdigest()
    template_id = hashlib.sha256(f'{GENERATOR_VERSION}:{cell_id}:{template_seed}'.encode()).hexdigest()
    clones = _clone_count(cell)
    base_count = cell.columns - clones
    rare = sorted(rng.sample(range(cell.rows), max(1, round(Fraction(str(cell.rare_row_proportion)) * cell.rows)))) if cell.family == 'redundant' else []
    rare_set = set(rare)
    blocks = []
    if cell.family == 'block':
        start = 0
        for b in range(cell.blocks):
            size = cell.columns // cell.blocks + (b < cell.columns % cell.blocks)
            blocks.append(list(range(start, start + size)))
            start += size
    rows, row_blocks, reductions = [], [], 0
    for r in range(cell.rows):
        if cell.family == 'block':
            b = rng.randrange(cell.blocks)
            row_blocks.append(b)
            inside_count = min((4 * cell.degree + 4) // 5, len(blocks[b]))
            reductions += inside_count < (4 * cell.degree + 4) // 5
            outside = [j for j in range(base_count) if j not in blocks[b]]
            row = rng.sample(blocks[b], inside_count) + rng.sample(outside, cell.degree - inside_count)
        else:
            degree = max(1, cell.degree // 4) if r in rare_set else cell.degree
            row = rng.sample(range(base_count), degree)
        rows.append(set(row))
    if cell.cost_distribution == 'uniform':
        costs = [rng.randint(1, 100) for _ in range(base_count)]
    else:
        costs = [rng.randint(1, 10) if rng.random() < cell.low_cost_probability else rng.randint(50, 100) for _ in range(base_count)]
    bridge = sorted({j for r in rare for j in rows[r]})
    eligible = [j for j in range(base_count) if j not in set(bridge)]
    if clones and not eligible:
        raise GenerationError(template_seed, clones, tuple(eligible))
    for j in bridge:
        costs[j] *= cell.bridge_multiplier
    sources = []
    for j in range(base_count, cell.columns):
        source = eligible[rng.randrange(len(eligible))]
        sources.append(source)
        for row in rows:
            if source in row:
                row.add(j)
        costs.append(max(1, costs[source] + rng.choice((-1, 0, 1))))
    indices, indptr = [], [0]
    for row in rows:
        indices.extend(sorted(row))
        indptr.append(len(indices))
    a = csr_matrix(([1] * len(indices), indices, indptr), shape=(cell.rows, cell.columns), dtype='uint8')
    for array in (a.data, a.indices, a.indptr):
        array.flags.writeable = False
    lineage = {'generator_version': GENERATOR_VERSION, 'cell': asdict(cell), 'template_seed': template_seed,
               'root_template_id': template_id, 'ancestor_template_ids': [], 'base_count': base_count,
               'clone_count': clones, 'clone_sources': sources, 'clone_eligible_columns': eligible,
               'clone_parent_rule': 'ordinary-base-no-rare-incidence-v1', 'recipe_amendment': 'A001',
               'rare_rows': rare, 'bridge_columns': bridge,
               'inside_reductions': reductions, 'row_blocks': row_blocks,
               'cost_order': ['bridge_base', 'clone', 'perturb_floor_one']}
    instance = CoverInstance('', template_id, cell_id, a, tuple(costs), lineage)
    return CoverInstance(instance_hash(instance), template_id, cell_id, a, tuple(costs), lineage)


def config_cells(config: dict[str, object]) -> list[GeneratorCell]:
    if config['purpose'] == 'workload':
        return [GeneratorCell(**cell) for cell in config['cells']]
    cells = []
    for n in config['column_counts']:
        for ratio in config['row_column_ratios']:
            m = int(n * ratio)
            for d in config['degrees']:
                for family in FAMILIES:
                    candidates = [GeneratorCell('block', n, m, d, blocks=b) for b in config['block_counts']] if family == 'block' else [GeneratorCell(family, n, m, d, clone_fraction=config['clone_fraction'] if family == 'redundant' else 0, bridge_multiplier=config['bridge_multiplier'] if family == 'redundant' else 1)]
                    for cell in candidates:
                        try:
                            validate_cell(cell)
                        except ValueError:
                            continue  # Explicit probe grid is restricted to valid recipe cells.
                        cells.append(cell)
    return cells


def generate_workload(config: dict[str, object], split: str, out: Path | None, *, dry_run: bool = False) -> dict[str, object]:
    return _generate_workload(config, split, out, dry_run=dry_run)


def generate_indexed_workload(config: dict[str, object], split: str, out: Path, *,
                              templates_per_cell: int, dry_run: bool = False) -> dict[str, object]:
    """Append rounds after the locked cell-major prefix without remapping it."""
    return _generate_workload(config, split, out, dry_run=dry_run, count=templates_per_cell)


def _generate_workload(config, split, out, *, dry_run=False, count=None):
    from ra.config import validate_config
    from ra.provenance import SplitOwnership, derive_seed
    validate_config(config, 'workload_probes' if config.get('purpose') == 'discovery' else 'workload')
    derive_seed(config['master_seed'], split, 0)
    if config['purpose'] == 'discovery' and split != 'discovery':
        raise ValueError('probe configuration is discovery-only')
    cells = config_cells(config)
    prefix = config['templates_per_cell']
    count = prefix if count is None else count
    if type(count) is not int or count < prefix:
        raise ValueError('append count must retain every locked prefix original')
    if not cells:
        raise ValueError('configuration has no valid cells')
    out = Path(out) if out is not None else Path('data') / split
    report = {'success': True, 'dry_run': dry_run, 'split': split, 'out': str(out), 'purpose': config['purpose'],
              'population_frozen': False, 'generator_version': GENERATOR_VERSION,
              'cells': [asdict(c) for c in cells], 'instance_count': len(cells) * count,
              'index_mapping': 'locked-cell-major-prefix-then-round-robin-v1',
              'templates_per_cell': count, 'prefix_templates_per_cell': prefix}
    if dry_run:
        return report
    if out.exists() and any(out.iterdir()):
        raise ValueError('generation output must be absent or empty')
    owner_path = out.parent / 'split_ownership.json'
    owners = SplitOwnership.load(owner_path) if owner_path.exists() else SplitOwnership()
    instances = []
    cell_indices = [c for c in range(len(cells)) for _ in range(prefix)]
    cell_indices += [c for _ in range(count - prefix) for c in range(len(cells))]
    for index, c_index in enumerate(cell_indices):
        instance = generate_cover(cells[c_index], derive_seed(config['master_seed'], split, index))
        owners.register(instance, split)
        instances.append((instance, index))
    configured_weights = config.get('family_weights') or {f: 1 for f in {c.family for c in cells}}
    total_weight = sum(configured_weights.values())
    family_counts = {f: sum(c.family == f for c in cells) for f in configured_weights}
    out.mkdir(parents=True, exist_ok=True)
    owners.save(owner_path)
    from ra.exact import canonical_cover
    records = []
    for instance, index in instances:
        payload = {**canonical_cover(instance), 'instance_id': instance.instance_id, 'template_id': instance.template_id,
                   'cell_id': instance.cell_id, 'lineage': instance.lineage}
        path = out / f'{instance.instance_id}.json'
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n')
        family = instance.lineage['cell']['family']
        records.append({'instance_id': instance.instance_id, 'template_id': instance.template_id, 'cell_id': instance.cell_id,
                        'template_index': index, 'family': family, 'path': path.name,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'population_weight': configured_weights[family] / total_weight / family_counts[family] / count})
    manifest = {**report, 'config': config, 'config_hash': hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'seed_scheme': 'sha256-json-v1', 'ownership_registry': str(owner_path), 'instances': records}
    (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    return manifest
