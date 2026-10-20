"""Saved-data/pure-control screen for an INACTIVE event-cap hypothesis.

This never loads the DEM engine, reconstructs or advances a physical state,
calls a force solver, changes a frozen binding, or creates execution authority.
The retained negative packet remains known-unaccepted throughout.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import lzma
import math
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / 'paper1_staging'
OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery04'
DEST = ROOT / 'paper1_designs/contact_event_cap_20261019/saved_screen_01'
DRIVER_SHA = '05447c49e219dfff6849f6b2c543037b894feaafa71be184db5f44133e69cf69'
CLOSURE_SHA = '6251eed02f4b3e5c3c4290f28f81cfd97edb364e2fc646866bc2234964045d25'
RAW_SHA = 'c2552e0f3a0ed1a3daa2633ad342510aadec41aea8da0e9734096d1f8cd3796e'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def dot(a, b):
    return math.fsum(x*y for x, y in zip(a, b))


def normal_row(normal, lever, ell):
    cross = [lever[1]*normal[2]-lever[2]*normal[1],
             lever[2]*normal[0]-lever[0]*normal[2],
             lever[0]*normal[1]-lever[1]*normal[0]]
    return list(normal)+[x/ell for x in cross]


def main(selector_sha, controls_sha):
    driver = STAGING/'run_stepdoubling_qualification_v4.py'
    assert sha(driver) == DRIVER_SHA
    run = module(driver, '_saved_event_screen_administration_only')
    run.environment()
    run.need(not DEST.exists(), 'one create-only saved-data decision screen')
    selector = STAGING/'contact_event_cap_v1.py'
    control = STAGING/'check_contact_event_cap_v1.py'
    run.need(sha(selector) == selector_sha and sha(control) == controls_sha,
             'caller-pinned inactive candidate and pure controls')
    closed_path = OUT/'final_execution_receipt_01/results.json'
    run.need(sha(closed_path) == CLOSURE_SHA, 'exact closed negative')
    closed = run.sealed(closed_path, positive=True)
    run.need(closed['closure_complete'] and not closed['qualified'], 'closed, never admitted case')
    identities = [row['launch'] for row in closed['exact_retirement_after']]
    before = run.assert_retired(identities)
    sources = {str(path): sha(path) for path in (Path(__file__).resolve(), driver, selector, control)}
    for relative in ('paper1_staging/full_state_integration_adapter_v3.py',
                     'paper1_staging/full_state_stepdoubling_v1.py',
                     'paper1_staging/contact_onset_timecap_v1.py',
                     'stage41_staging/inertial_contact_cold_optimized_v1.py',
                     'stage50_staging/inertial_contact_seeded_lm_v1.py',
                     'stage74_staging/inertial_contact_scalar_kernel_v1.py',
                     'stage212_staging/roundoff_sphere_gap_v1.py'):
        path = ROOT/relative
        run.need(sha(path) == closed['source_files'][str(path)], 'unchanged consumed original source '+relative)
        sources[str(path)] = sha(path)
    raw = OUT/'records/f0p0625_production_00149/packet.json.xz'
    run.need(sha(raw) == RAW_SHA == closed['artifacts'][str(raw)], 'exact immutable negative raw')
    packet = json.loads(lzma.decompress(raw.read_bytes()))['packet']
    run.need(packet['status'] == 'negative' and packet['work_rows'] == 1725
             and 'bounded accuracy rejection' in packet['error'], 'retained negative, not a new admission')
    branches = packet['work_branches'][-27:]
    origin = branches[0]['before_state']
    prepare = branches[0]['normal_gap_operand_policy']['prepare_calls'][0]
    grain, gap, normal, lever = prepare['contacts'][0]
    run.need(grain == 15 and gap > 0 and prepare['effective_gaps_m'] == [gap]
             and prepare['metadata'][0]['classification']['sphere'] is False
             and prepare['metadata'][0]['classification']['changed'] is False,
             'positive original fibre gap, no sphere-band substitution')
    row = normal_row(normal, lever, prepare['ell_m'])
    row_norm = math.sqrt(dot(row, row))
    closing = -dot(row, origin['q'])
    run.need(closing > 0, 'same-origin closing tangent exists')
    limits = packet['limits']; speed = limits['speed_m_s']; eps = limits['velocity_defect_over_U']
    cap = packet['cursor_after']['original_selected_cap_s']; minimum = limits['minimum_h_s']
    table = []
    for depth in range(9):
        c, f1, f2 = branches[depth*3:depth*3+3]
        h = c['requested_dt_s']
        run.need(all(b['before_state']['t'] == origin['t'] for b in (c, f1))
                 and c['after_state']['t'] == f2['after_state']['t'] == origin['t']+h
                 and f1['after_state']['t'] == origin['t']+h/2,
                 'actual decreasing literal retry clocks and shared origin')
        run.need(h == cap/2**depth, 'eight actual halvings, not stale cursor preflight execution')
        dq = [a-b for a, b in zip(c['after_state']['q'], f2['after_state']['q'])]
        norm = math.sqrt(dot(dq, dq))/speed
        table.append(dict(depth=depth, requested_h_s=h, actual_end_s=c['after_state']['t'],
                          saved_velocity_defect_over_U=norm,
                          exact_saved_normal_projection_lower_bound_over_U=abs(dot(row,dq))/(row_norm*speed),
                          scaled_velocity_defect=norm/eps, h_times_defect_s=h*norm))
    factor_screen = []
    for factor in (.125, .0625, .03125):
        # Source-scaled cap proxy at the SAME saved physical state; no fresh
        # geometry/field/mobility assembly or native trajectory is performed.
        proxy_cap = cap*(factor/.0625)
        level_eps = eps*(factor/.0625)**2
        for release_fraction in (.125, .5):
            threshold = release_fraction*speed*level_eps*proxy_cap
            count = max(0, math.ceil(math.log2(gap/threshold)))
            last = gap/closing/2**count if count else proxy_cap
            factor_screen.append(dict(factor=factor, release_fraction=release_fraction,
                original_cap_source_scaled_proxy_s=proxy_cap, unchanged_local_velocity_limit_over_U=level_eps,
                release_proxy_gap_m=threshold, ideal_precontact_half_gap_steps=count,
                ideal_last_precontact_macro_s=last, fixed_minimum_macro_s=minimum,
                ideal_minimum_step_feasible=last >= minimum,
                release_proxy_over_max_coordinate_ulp=threshold/max(math.ulp(x) for x in origin['x']),
                proxy_not_a_native_step_or_certified_event_root=True))
    tests = subprocess.run([sys.executable,'-B',str(control)], cwd=ROOT,env=os.environ.copy(),
                           capture_output=True,text=True,timeout=120)
    run.need(tests.returncode == 0, 'actual pure-control execution must pass')
    match = re.search(r'Ran (\d+) tests',tests.stderr)
    for path, expected in sources.items():run.need(sha(path) == expected,'consumed source stayed fixed')
    body = dict(schema='paper1.event-cap.saved-data-and-pure-screen.v1',passed=True,utc=run.utc(),
        source_files=sources,closed_execution_receipt_sha256=CLOSURE_SHA,negative_raw_sha256=RAW_SHA,
        negative_raw_known_unaccepted_rows_unchanged=1725,original_goal_dataset_qualified_cases=1,
        original_goal_dataset_required_cases=12,retirement_before=before,retirement_after=run.assert_retired(identities),
        origin_time_s=origin['t'],original_gap_m=gap,normal_jacobian=row,normal_jacobian_norm=row_norm,
        saved_old_closing_m_s=closing,frozen_velocity_limit_m_s=speed*eps,
        original_selected_cap_s=cap,old_velocity_tangent_touch_time_s=gap/closing,
        time_ulp_s=math.ulp(origin['t']),coordinate_ulps_m=[math.ulp(x) for x in origin['x']],
        conditional_zero_F2_gap_active_regime_required_h_s=gap/(speed*eps*row_norm),
        conditional_active_regime_bound_not_a_global_unsolved_branch_bound=True,
        actual_saved_trial_table=table,idealized_factor_and_release_screen=factor_screen,
        pure_controls=dict(returncode=tests.returncode,test_count=None if match is None else int(match.group(1)),
                           stdout=tests.stdout,stderr=tests.stderr),
        decision='Inactive finite precontact-cap hypothesis; fixed one-eighth release rejected by finer minimum-step screen; one-half release still needs coupled native falsification.',
        limitations=['Old-q tangent is not an authenticated event root or a bound on changing free-flight velocity.',
                     'Scalar normal-gap release does not bound generalized velocity under friction or multiple contacts.',
                     'Geometry quantization remains unchanged; no fibre snapping or sphere-band extension is permitted.',
                     'Source-scaled caps and exact one-dimensional toy controls are not actual DEM outcomes.',
                     'No whole raw/history mechanical replay, original gate pass, failed-packet admission or fresh seed qualification is claimed.'],
        adapter_integration_prepared=False,independent_native_qualification_completed=False,
        dispatch_authorized=False,execution_authority_created=False,new_clock_created=False,
        new_force_calls=0,new_transport_steps=0,new_integration_records=0,
        frozen_local_original_accuracy_physics_gap_and_route_gates_unchanged=True)
    run.seal(DEST,body)
    print('SAVED_EVENT_CAP_SCREEN',run.sha(DEST/'results.json'),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selector_sha256');parser.add_argument('controls_sha256')
    args=parser.parse_args();main(args.selector_sha256,args.controls_sha256)
