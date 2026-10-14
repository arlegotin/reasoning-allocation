"""Scientific gates: unavailable literature is never counted as defeated."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from ra import config


def validate(register, cards):
    assert hasattr(config, 'validate_baseline_register'), 'baseline register validation missing'
    config.validate_baseline_register(register, cards)


def blob(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True))
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


GATES = ('cpu_inference', 'cpu_backward', 'serialization', 'operators', 'live_features',
         'hybrid_handoff', 'tiny_optimum', 'original_reproduction', 'cpu_resources')


@pytest.fixture
def record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audit = blob(Path('audit.json'), {'scope': 'test-only access evidence'})
    selected = {key: {'name': key, 'kind': 'native', 'overrides': {}}
                for key in ('B0', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6')}
    register = {'schema_version': 1, 'selected': selected,
                'control_pins': {key: digest(value) for key, value in selected.items()},
                'comparison_ids': list(selected), 'claims': [], 'evidence': [audit]}
    card = {'schema_version': 1, 'id': 'labassi', 'method': 'Labassi', 'status': 'blocked',
            'source': {'paper_url': 'https://example.org/paper', 'paper_revision': 'v1',
                       'repository_url': 'https://example.org/repo', 'commit': 'a' * 40,
                       'software_license': None, 'paper_license': 'unresolved',
                       'inspected': ['selector.py lines 1-10']},
            'permissions': {key: {'status': 'unresolved', 'terms': 'not established', 'evidence': [audit]}
                            for key in ('code', 'checkpoints', 'teacher_assets', 'dependencies')},
            'original_regime': {key: 'unresolved' for key in ('architecture', 'loss', 'depth_weighting',
                              'teacher', 'candidate_comparison', 'hybrid_handoff', 'solver', 'hardware')},
            'changes': [], 'adapted_from': None, 'configuration': None, 'entry_point': None,
            'gates': {key: {'state': 'not_run', 'reason': 'author-code permission unresolved', 'evidence': []}
                      for key in GATES},
            'resources': {'measured': False, 'costs': None, 'failed_attempts': [],
                          'notes': 'No execution; hardware feasibility unmeasured'},
            'blockers': ['author-code permission unresolved'], 'evidence': [audit]}
    return register, [card]


def executable(record):
    register, cards = record
    card = cards[0]
    card['status'] = 'reproduced'
    card['blockers'] = []
    card['source']['software_license'] = 'MIT (test fixture only)'
    for term in card['permissions'].values():
        term['status'] = 'granted'
        term['terms'] = 'MIT (test fixture only)'
    card['configuration'] = {'id': 'labassi-original', **blob(Path('original.json'), {'purpose': 'test-only'})}
    card['entry_point'] = blob(Path('port.py'), {'purpose': 'test-only non-executed pin'})
    card['resources'].update(measured=True, costs={'teacher_cpu_ns': 0, 'training_cpu_ns': 1,
                                                'inference_cpu_ns': 1, 'peak_rss_bytes': 1})
    for key in GATES:
        ref = blob(Path(f'{key}.json'), {'baseline_id': card['id'], 'gate': key, 'success': True,
                   'source_commit': card['source']['commit'], 'config_sha256': card['configuration']['sha256']})
        card['gates'][key] = {'state': 'passed', 'reason': 'test fixture only', 'evidence': [ref]}
    register['comparison_ids'].append(card['id'])
    return register, cards


def test_blocked_cards_allow_core_to_proceed(record):
    validate(*record)


@pytest.mark.parametrize('status', ['blocked', 'reference_only', 'approximation'])
def test_unavailable_or_approximate_method_cannot_be_counted_as_beaten(record, status):
    register, cards = record
    cards[0]['status'] = status
    if status == 'approximation':
        cards[0].update(method='Labassi-inspired approximation', changes=['independent approximation'])
    register['claims'] = [{'baseline_id': 'labassi', 'kind': 'named_superiority', 'evidence': register['evidence']}]
    with pytest.raises(ValueError):
        validate(register, cards)


@pytest.mark.parametrize('control', ['B0', 'B1', 'B3', 'B4', 'B5', 'B6'])
def test_required_control_cannot_disappear(record, control):
    register, cards = record
    del register['selected'][control]
    with pytest.raises(ValueError):
        validate(register, cards)


def test_control_must_remain_in_comparisons(record):
    register, cards = record
    register['comparison_ids'].remove('B1')
    with pytest.raises(ValueError):
        validate(register, cards)


def test_control_configuration_cannot_drift_from_pin(record):
    register, cards = record
    register['selected']['B1']['overrides']['unreviewed'] = 2
    with pytest.raises(ValueError):
        validate(register, cards)


def test_dependency_grant_does_not_grant_author_code(record):
    register, cards = executable(record)
    cards[0]['permissions']['code']['status'] = 'unresolved'
    with pytest.raises(ValueError):
        validate(register, cards)


def test_checkpoint_permission_is_independent(record):
    register, cards = executable(record)
    cards[0]['permissions']['checkpoints']['status'] = 'unresolved'
    with pytest.raises(ValueError):
        validate(register, cards)


def test_reproduced_contender_cannot_be_excluded_for_outperforming_candidate(record):
    register, cards = executable(record)
    register['comparison_ids'].remove('labassi')
    with pytest.raises(ValueError):
        validate(register, cards)


def test_reproduced_fixture_is_accepted(record):
    validate(*executable(record))


def adaptation(record):
    register, cards = executable(record)
    card = deepcopy(cards[0])
    card.update(id='labassi-common', method='Labassi common-build adaptation', status='adapted',
                adapted_from='labassi', changes=['common solver build'])
    card['configuration'] = {'id': 'labassi-common-build', **blob(Path('adapted.json'), {'purpose': 'test-only common build'})}
    for key in GATES:
        card['gates'][key]['evidence'] = [blob(Path(f'adapted/{key}.json'), {
            'baseline_id': 'labassi-common', 'gate': key, 'success': True, 'source_commit': 'a' * 40,
            'config_sha256': card['configuration']['sha256']})]
    cards.append(card)
    register['comparison_ids'].append('labassi-common')
    return register, cards


def test_source_matched_adaptation_with_distinct_config_and_evidence_is_accepted(record):
    validate(*adaptation(record))


def test_adapted_contender_cannot_make_unqualified_named_claim(record):
    register, cards = adaptation(record)
    register['claims'] = [{'baseline_id': 'labassi-common', 'kind': 'named_superiority', 'evidence': register['evidence']}]
    with pytest.raises(ValueError):
        validate(register, cards)


def test_access_audit_cannot_serve_as_superiority_outcome_evidence(record):
    register, cards = executable(record)
    register['claims'] = [{'baseline_id': 'labassi', 'kind': 'named_superiority', 'evidence': register['evidence']}]
    with pytest.raises(ValueError):
        validate(register, cards)


def test_direct_card_construction_cannot_bypass_validation(record):
    from ra.baselines import BaselineCard
    _, cards = record
    cards[0]['status'] = 'invented'
    with pytest.raises(ValueError):
        BaselineCard(**cards[0])


def test_full_register_cannot_drop_a_locked_literature_card():
    from ra.baselines.register import load_register
    register, cards = load_register(Path('configs/mandatory_baselines.json'))
    with pytest.raises(ValueError):
        validate(register, cards[:-1])


def test_full_register_cannot_remove_a_required_named_disposition():
    from ra.baselines.register import load_register
    register, cards = load_register(Path('configs/mandatory_baselines.json'))
    register['baseline_register']['cards'].pop()
    with pytest.raises(ValueError):
        validate(register, cards[:-1])


def test_full_register_cannot_promote_a_locked_card_without_evidence_update():
    from ra.baselines.register import load_register
    register, cards = load_register(Path('configs/mandatory_baselines.json'))
    cards[0]['status'] = 'reference_only'
    with pytest.raises(ValueError):
        validate(register, cards)


def test_claimed_parity_requires_hash_addressed_evidence(record):
    register, cards = executable(record)
    del cards[0]['gates']['live_features']['evidence'][0]['sha256']
    with pytest.raises(ValueError):
        validate(register, cards)


def test_gate_evidence_binds_the_actual_configuration(record):
    register, cards = executable(record)
    ref = blob(Path('wrong-gate.json'), {'baseline_id': 'labassi', 'gate': 'live_features', 'success': True,
               'source_commit': 'a' * 40, 'config_sha256': '0' * 64})
    cards[0]['gates']['live_features']['evidence'] = [ref]
    with pytest.raises(ValueError):
        validate(register, cards)


def test_changed_evidence_bytes_are_rejected(record):
    register, cards = record
    Path(register['evidence'][0]['path']).write_text('changed')
    with pytest.raises(ValueError):
        validate(register, cards)


def test_shared_build_adaptation_needs_own_config_and_evidence(record):
    register, cards = executable(record)
    adapted = deepcopy(cards[0])
    adapted.update(id='labassi-common', status='adapted', adapted_from='labassi', changes=['common solver build'])
    cards.append(adapted)
    register['comparison_ids'].append('labassi-common')
    with pytest.raises(ValueError):
        validate(register, cards)


def test_approximation_must_have_explicitly_different_method_name(record):
    register, cards = record
    cards[0].update(status='approximation', blockers=[], changes=['independent paper-inspired model'])
    with pytest.raises(ValueError):
        validate(register, cards)


@pytest.mark.parametrize('baseline', ['labassi', 'mattick-mutschler', 'trgnn', 'deepbound', 'treecl'])
@pytest.mark.parametrize('dry_run', [False, True])
def test_reproduce_rejects_blocked_card_without_output(tmp_path, capsys, baseline, dry_run):
    from ra.cli import main
    out = tmp_path / 'reproduction'
    args = ['reproduce', '--baseline', baseline, '--config', 'configs/mandatory_baselines.json', '--out', str(out)]
    assert main(args + (['--dry-run'] if dry_run else [])) == 1
    assert 'blocked' in capsys.readouterr().err
    assert not out.exists()


def test_configuration_bound_comparison_evidence_allows_scoped_named_claim(record):
    register, cards = executable(record)
    evidence = blob(Path('comparison.json'), {'baseline_id': 'labassi', 'kind': 'named_superiority',
                    'source_commit': 'a' * 40, 'config_sha256': cards[0]['configuration']['sha256'],
                    'comparison_complete': True, 'scope': 'test-only synthetic comparison', 'outcome': 'candidate_superior'})
    register['claims'] = [{'baseline_id': 'labassi', 'kind': 'named_superiority', 'evidence': [evidence]}]
    validate(register, cards)


def test_blocked_card_cannot_hide_cpu_cost_as_measured_zero(record):
    register, cards = record
    cards[0]['resources']['costs'] = {'teacher_cpu_ns': 0, 'training_cpu_ns': 0, 'inference_cpu_ns': 0, 'peak_rss_bytes': 0}
    with pytest.raises(ValueError):
        validate(register, cards)


def test_gate_missing_blocks_reproduction(record):
    register, cards = executable(record)
    cards[0]['gates']['cpu_backward'].update(state='not_run', evidence=[])
    with pytest.raises(ValueError):
        validate(register, cards)


@pytest.mark.parametrize('location', ['status', 'permission', 'gate', 'claim'])
def test_malformed_enum_is_a_validation_error(record, location):
    register, cards = record
    if location == 'status':
        cards[0]['status'] = ['blocked']
    elif location == 'permission':
        cards[0]['permissions']['code']['status'] = ['unresolved']
    elif location == 'gate':
        cards[0]['gates']['cpu_inference']['state'] = ['not_run']
    else:
        register['claims'] = [{'baseline_id': ['labassi'], 'kind': ['named_superiority'], 'evidence': []}]
    with pytest.raises(ValueError):
        validate(register, cards)


def test_own_named_reproduction_does_not_dispatch_arbitrary_pinned_script(record, capsys):
    from ra.cli import main
    blocked = deepcopy(record[1][0])
    register, cards = executable(record)
    for baseline in ['mattick-mutschler', 'trgnn', 'deepbound', 'treecl']:
        other = deepcopy(blocked)
        other['id'] = baseline
        cards.append(other)
    pinned = {'schema_version': 1, 'selected': register['selected'], 'baseline_register': {
        key: value for key, value in register.items() if key != 'selected'}}
    pinned['baseline_register']['cards'] = []
    for card in cards:
        path = Path(card['id'] + '.md')
        path.write_text('```json\n' + json.dumps(card) + '\n```\n')
        pinned['baseline_register']['cards'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    Path('register.json').write_text(json.dumps(pinned))
    assert main(['reproduce', '--baseline', 'labassi', '--config', 'register.json', '--out', 'out']) == 1
    assert 'no permitted executable port installed' in capsys.readouterr().err
    assert not Path('out').exists()


def test_locked_register_malformed_supplied_id_is_validation_error():
    register=json.loads(Path('configs/mandatory_baselines.json').read_text())
    from ra.baselines.register import read_card
    cards=[read_card(ref) for ref in register['baseline_register']['cards']]
    cards[0]['id']=[]
    with pytest.raises(ValueError): validate(register,cards)
