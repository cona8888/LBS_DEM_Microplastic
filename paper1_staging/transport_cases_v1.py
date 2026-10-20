"""Prospective Paper1 cases copied from the qualified physical specification.

Case construction is not dispatch authority. Screen records are diagnostic;
core cases additionally require a sealed prospective exposure decision.
"""
from pathlib import Path
import copy, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'paper1_staging'))
import load_direct_fields_v1 as fields
CONTRACT = ROOT / 'paper1_designs/mechanism_feasibility_20261013/contract_01.json'
CONTRACT_SHA = 'e04f863f6297581efe42606e1c3125b4105a17b2af081a685173dc9f1d4f7166'
EXPOSURE = CONTRACT.parent / 'exposure_decision_01/results.json'
SCALED_CONTROLS = ('angle_limit_rad', 'displacement_fraction', 'max_dt_s', 'relaxation_fraction')


def contract():
    fields.require(fields.sha(CONTRACT) == CONTRACT_SHA, 'Paper1 contract changed')
    result = fields.read(CONTRACT)
    fields.require(fields.sha(result['physical_design_file']) == result['physical_design_sha256'],
                   'Original physical specification changed')
    return result


def case_for(core_id, metadata, exposure_pv, factor=.125, mode='screen'):
    c = contract()
    core = next((x for x in c['cases'] if x['id'] == core_id), None)
    fields.require(core is not None and mode in ('screen', 'core'), 'Unknown prospective case/mode')
    fields.require(exposure_pv in c['exposure_selection']['candidate_pv'] and factor in (.125, .0625, .03125),
                   'Outside prospective exposure/refinement domain')
    fields.require(metadata['cpd'] == core['cpd'] == 6 and metadata['flow_factor'] == core['nominal_flow_level']
                   and metadata['normalization_to_target_applied'] is False,
                   'Exact direct flow and unchanged SI convention required')
    mean = metadata['achieved_mean_interstitial_velocity_m_s']
    length = metadata['cell_length_m']
    fields.require(mean > 0 and length > 0 and abs(metadata['pv_per_second'] / (mean / length) - 1) < 1e-14,
                   'Achieved-flow pore-volume clock')
    if mode == 'core':
        decision = fields.sealed(EXPOSURE)
        fields.require(decision['passed'] and decision['contract_sha256'] == CONTRACT_SHA
                       and decision['selected_pv'] == exposure_pv and decision['frozen_before_core_comparisons'],
                       'Core exposure not prospectively admitted')
    d = fields.read(c['physical_design_file'])
    template = next(x for x in d['cases'] if x['sample_id'] == core['placement_id']
                    and x['shape'] == core['shape'] and x['factor'] == .125)
    result = copy.deepcopy(template)
    suffix = 'f' + str(factor).replace('.', 'p')
    result.update(id=core_id + '_' + mode + '_' + suffix,
                  role='discarded_cost_accuracy_screen' if mode == 'screen' else 'conditional_paper1_core',
                  factor=factor, placement_id=core['placement_id'], reference_case=None)
    spec = result['spec']
    cfg = spec['config']
    spec.update(case_id=result['id'], sample_id=core['placement_id'], flow_factor=core['nominal_flow_level'],
                field_metadata=copy.deepcopy(metadata), horizon_pv=exposure_pv,
                horizon_s=exposure_pv * length / mean, nominal_speed_m_s=.0001 * core['nominal_flow_level'])
    expected = next(x['initial_state'] for x in c['placements'] if x['id'] == core['placement_id'])
    fields.require(spec['initial_state'] == expected, 'Paired initial state drift')
    # .125 is the outer numerical-factor label, not spec.refinement: setting the
    # latter to .125 would accidentally coarsen the original step controls 16x.
    fields.require(template['spec']['refinement'] == .0078125, 'Qualified refinement convention changed')
    ratio = factor / .125
    spec['refinement'] *= ratio
    for key in SCALED_CONTROLS:
        cfg['numerics'][key] *= ratio
    cfg.update(horizon_pore_volumes=exposure_pv, target_mean_interstitial_velocity_m_s=mean,
               packings=[dict(seed=2, sample_id=core['placement_id'])],
               purpose='Conditional paired shape-flow mechanisms at one packing and two labelled placements.',
               claim_boundary='No population release probability, universal shape ranking or environmental validation.',
               status='prospective_paper1_' + mode)
    return result


def load_case(core_id, exposure_pv, factor=.125, mode='screen'):
    c = contract()
    core = next(x for x in c['cases'] if x['id'] == core_id)
    field, geometry, metadata = fields.load(2, core['nominal_flow_level'], 6)
    return case_for(core_id, metadata, exposure_pv, factor, mode), field, geometry
