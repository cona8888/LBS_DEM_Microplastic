"""Freeze a CPD6 geometry and bounded GPU-throughput diagnostic, not a flow solution."""
from __future__ import annotations

import ctypes
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage114_staging'))
import requalify_stationary_flows_v1 as prior
sys.path.insert(0, str(ROOT / 'stage27_staging'))
import build_stage27a_mechanics_hydraulic_masks_v1 as geom

STUDY = 'third_grid_cost_20260916'
BASE = ROOT / 'stage125_designs' / STUDY
DESIGN = BASE / 'design_01.json'
EVAL = ROOT / 'stage125_evaluations' / STUDY
RUN = ROOT / 'stage125_runs' / STUDY / 'gpu_pilot_01'
PREFLIGHT = EVAL / 'preflight_01/results.json'
read, write, require, bind = prior.audit.read, prior.write, prior.require, prior.bind
sha = prior.audit.sha


def digest_array(a):
    a = np.ascontiguousarray(a)
    return hashlib.sha256(memoryview(a).cast('B')).hexdigest()


def device_bytes(n):
    # Two D3Q19 float32 states, one uint8 mask, one int32 health flag.
    return (2 * 19 * 4 + 1) * int(n)**3 + 4


def available_ram():
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (k, ctypes.c_ulonglong) for k in ['total', 'available', 'total_page', 'available_page',
                                             'total_virtual', 'available_virtual', 'extended']]
    value = Memory()
    value.length = ctypes.sizeof(value)
    require(bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value))), 'RAM query failed')
    return {'total_bytes': int(value.total), 'available_bytes': int(value.available)}


def gpu_snapshot():
    command = ['nvidia-smi', '--query-gpu=name,memory.total,memory.free,utilization.gpu,temperature.gpu',
               '--format=csv,noheader,nounits']
    result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    rows = [x.strip() for x in result.stdout.strip().splitlines()]
    require(len(rows) == 1, 'expected exactly one GPU')
    name, total, free, use, temperature = [x.strip() for x in rows[0].split(',')]
    return {'name': name, 'total_bytes': int(total)*1048576, 'free_bytes': int(free)*1048576,
            'utilization_percent': int(use), 'temperature_C': int(temperature)}


def verify(d):
    prior.verify_bindings(d['bindings'])
    require(d['pilot']['steps'] == 417 and d['pilot']['cpd'] == 6, 'pilot scope changed')
    require(not d['authority']['transport'] and not d['authority']['full_steady_solve'], 'authority widened')
    require(d['geometry']['shape_zyx'] == [279]*3, 'grid drift')


def prepare():
    require(not BASE.exists(), 'immutable design directory already exists')
    previous = read(prior.DESIGN)
    prior.verify_design(previous)
    evidence_path = ROOT / 'stage114_evaluations' / prior.STUDY / 'independent_evaluation_01/results.json'
    evidence = read(evidence_path)
    evidence_done = read(evidence_path.with_name('completion.json'))
    require(evidence['passed'] and evidence_done['results_sha256'] == sha(evidence_path), 'field qualification drift')
    spec4 = next(c for c in previous['cases'] if c['cpd'] == 4)
    ref4 = next(c for c in evidence['cases'] if c['cpd'] == 4)
    prior.verify_bindings(ref4['bundle'])
    stage124 = ROOT / 'stage124_evaluations/mean_offset_attribution_20260916/completion.json'
    seal = read(stage124)
    require(seal['status'] == 'mean_offset_attribution_complete_spatial_gate_open', 'attribution absent')
    for path, expected in seal['artifacts'].items():
        require(sha(path) == expected, 'Stage124 drift: ' + path)
    with np.load(spec4['geometry']['path'], allow_pickle=False) as data:
        source = {k: data[k] for k in data.files}
    length = float(source['cell_length_m'][0])
    # Same cell-centre sphere union, no grain resizing/repacking or smoothed wall.
    mask = np.zeros((279,)*3, dtype=bool)
    geom.mark_spheres(mask, source['sand_centres_m'], source['sand_radii_m'], length)
    phase = np.where(mask, 2, 0).astype(np.uint8)
    BASE.mkdir(parents=True)
    path = BASE / 'geometry_cpd6.npz'
    np.savez_compressed(path, phase=phase, material=mask.astype(np.uint8),
        spacing_m=np.array([length/279]), cell_length_m=source['cell_length_m'],
        original_cell_lengths_m=source['original_cell_lengths_m'], affine_scale_xyz=source['affine_scale_xyz'],
        sand_centres_m=source['sand_centres_m'], sand_radii_m=source['sand_radii_m'],
        fibre_centrelines_m=source['fibre_centrelines_m'], fibre_radius_m=source['fibre_radius_m'])
    legacy = prior.audit.legacy
    module_paths = [Path(__file__), Path(geom.__file__), Path(prior.__file__), Path(prior.audit.__file__),
                    Path(prior.probe.__file__), Path(prior.gate.__file__)]
    module_paths += [Path(m.__file__) for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                     and Path(m.__file__).suffix == '.py' and str(prior.audit.EXTERNAL) in str(m.__file__)]
    module_paths += list((ROOT/'stage125_staging').glob('*.py'))
    bindings = {str(p.resolve()): bind(p) for p in sorted(set(module_paths))}
    bindings.update({'prior_design': bind(prior.DESIGN), 'prior_evaluation': bind(evidence_path),
        'prior_evaluation_completion': bind(evidence_path.with_name('completion.json')),
        'stage124_seal': bind(stage124), 'source_geometry': spec4['geometry'], 'geometry_cpd6': bind(path),
        'prior_cpd4_bundle': ref4['bundle'], 'cuda_source': previous['lineage']['cuda_source']})
    acceleration = float(np.float32(spec4['acceleration_lu'] * (186/279)**3))
    reference_record = Path(spec4['source']['record'])
    bindings['historical_cost_record'] = bind(reference_record)
    old_cost = read(reference_record)
    d = {'schema': 'matdem.stage125.spatial-cost.v1', 'created_utc': datetime.now(timezone.utc).isoformat(),
         'question': 'Can a third directly solved grid fit the available hardware and a bounded cost budget?',
         'claim_boundary': 'Cost/geometry/transition verification only. Cold 417-step pilot is not steady, not mean-matched and not a transport input.',
         'bindings': bindings, 'qualified_ptx_sha256': previous['lineage']['qualified_ptx_sha256'],
         'geometry': {'path': str(path), 'shape_zyx': [279]*3, 'cpd': 6, 'spacing_m': length/279,
                      'cell_length_m': length, 'phase_array_sha256': digest_array(phase),
                      'grain_count': len(source['sand_radii_m']), 'voxel_porosity': float(np.mean(phase==0))},
         'pilot': {'cpd': 6, 'steps': 417, 'warmup_steps': 32, 'timed_blocks': 3, 'steps_per_block': 128,
                   'final_transition_steps': 1, 'tau': .8, 'nu_lu': .1, 'threads': 256,
                   'initialization': 'zero shifted populations (rho=1, no stored momentum); cost pilot only',
                   'acceleration_lu': acceleration, 'forcing_rule': 'CPD4 acceleration times (dx6/dx4)^3, fixed SI viscosity scaling; not a mean-flow match',
                   'wall_budget_s': 900, 'check_interval_steps': 32, 'cpu_transition_nodes': 64,
                   'gpu_reserve_bytes': 3*1024**3, 'minimum_available_ram_bytes': 12*1024**3,
                   'maximum_start_temperature_C': 75, 'maximum_run_temperature_C': 82,
                   'transition_relative_l2_max': 5e-5, 'transition_absolute_max': 2e-7},
         'cost_model': {'device_bytes': device_bytes(279), 'host_working_set_planning_bytes': 8*1024**3,
                        'historical_cpd4_steps': old_cost['steps_completed'],
                        'historical_cpd4_kernel_s': old_cost['performance']['kernel_seconds'],
                        'scenario_steps': [20000, 100000, 198000], 'full_solve_budget_s': 6*3600,
                        'scenario_time_safety_multiplier': 1.25,
                        'limitation': 'Throughput projections are conditional on assumed step counts, not convergence predictions. 198000 is 88000*(6/4)^2, a diffusion-time heuristic; the old even-parity gate was insufficient.'},
         'next_spatial_protocol': {
             'packings': [2], 'grids_cpd': [2,4,6], 'sand_state': 'identical periodic 216-grain state',
             'target_mean_velocity_m_s': ref4['mean_interstitial_velocity_m_s'],
             'achieved_mean_relative_error_max_each': .0005,
             'mean_control': 'Adjust body force only between independently converged solves; freeze final force then requalify. No scaling of final velocity arrays.',
             'steady_gate': bind(prior.gate.__file__),
             'independent_field_relative_l2_max': 2e-6, 'cpu_collision_relative_l2_max': 5e-5,
             'trajectory_query_s': .5, 'shapes': ['equal_volume_sphere','rigid_prolate_ar4'],
             'same_initial_state': 'Stage121/122 seed2 original common-admissible sample 0',
             'temporal_policy': 'At least three cap levels at every new field; retain previous failures; further levels need declared versioned refinement.',
             'response_budget': {'position_over_minor_radius_max': .02, 'apolar_axis_rad_max': .01,
                                 'velocity_over_fixed_scale_max': .05,
                                 'rule': 'Require CPD4/CPD6 difference plus twice both adjacent temporal differences within each threshold. Require decreasing CPD2/4 to CPD4/6 differences; if unresolved, no pass.',
                                 'rationale': 'Reuse the existing short-time numerical accuracy goals; not a release-fraction uncertainty bound. Fixed velocity scale per shape is max(CPD4 speed, common mean).'},
             'contrast_policy': 'Report paired fibre-minus-sphere travel shift and its temporal allowance; no population effect, release ranking or asymptotic Richardson order from voxel grids.',
             'near_wall_policy': 'Probe all resolutions at identical physical poses; retain mixed-wall samples separately; never drop them to improve RMS.',
             'cost_gate': 'A bounded warm-start pilot and convergence-rate evidence must fit the six-hour study budget before full solve dispatch.'},
         'authority': {'geometry': True, 'bounded_cost_pilot': True, 'full_steady_solve': False,
                       'transport': False, 'population': False, 'empirical_validation': False}}
    verify(d)
    write(DESIGN, d)
    print(json.dumps({'design': str(DESIGN), 'sha256': sha(DESIGN), 'device_GiB': device_bytes(279)/1024**3}), flush=True)


if __name__ == '__main__':
    prepare()
