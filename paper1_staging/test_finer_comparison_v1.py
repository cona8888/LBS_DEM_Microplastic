"""Zero-transport tests of the separately versioned adjacent-refinement comparator."""
from pathlib import Path
import ast
import copy
import json
import sys
import tempfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_core_v1 as old
import compare_core_v2 as new


def run():
    destination = new.s.ROOT / 'paper1_designs/p1_i0_fibre_u0p5_accuracy_recovery_20261014/comparator_qualification_01'
    new.api.require(not destination.exists(), 'Create-only qualification')
    checks = {}
    def reject(name, action):
        try:
            action()
        except (RuntimeError, ValueError, AssertionError, KeyError):
            checks[name] = True
        else:
            raise AssertionError('Negative control admitted: ' + name)

    a = Path(old.__file__).read_text(encoding='utf-8')
    b = Path(new.__file__).read_text(encoding='utf-8')
    needle = "api.require(a['factor']==.125 and b['factor']==.0625,'Prospective original-control finer reference')"
    replacement = "api.require((a['factor'],b['factor']) in ((.125,.0625),(.0625,.03125)),'Only declared adjacent original-control refinements')"
    checks['only_adjacent_factor_domain_changed'] = a.count(needle) == 1 and a.replace(needle, replacement) == b
    def function_tree(text, name):
        return ast.dump(next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name))
    checks['full_raw_authentication_unchanged'] = function_tree(a, 'authenticate') == function_tree(b, 'authenticate')
    checks['physical_signature_unchanged'] = function_tree(a, 'physical_signature') == function_tree(b, 'physical_signature')
    checks['original_metric_and_gate_objects'] = (new.s.q.job.path_metrics.metrics is old.s.q.job.path_metrics.metrics
        and new.s.q.job.policy.pair_gates is old.s.q.job.policy.pair_gates)
    gates = new.s.read(new.s.factory.contract()['physical_design_file'])['numerical_gates']
    checks['all_original_thresholds_unchanged'] = gates == new.s.q.job.policy.GATES
    proposal = new.s.ROOT / 'paper1_designs/p1_i0_fibre_u0p5_accuracy_recovery_20261014/proposal_01.json'
    case = new.s.read(proposal)['physical_case']
    H = case['spec']['horizon_s']
    U = case['spec']['config']['target_mean_interstitial_velocity_m_s']
    radius = case['spec']['config']['prolate_semiaxes_m'][1]
    initial = case['spec']['initial_state']
    pose = np.array([*initial['position_m'], *initial['orientation']])
    def rows(times, dx=0., dq=0.):
        out = np.zeros((len(times), 13)); out[:, 0] = times; out[:, 1:7] = pose
        out[:, 1] += dx; out[:, 7] = dq
        return out
    observation = dict(complete_observation=True, status='present_at_horizon', start_s=0., stop_s=H,
                       first_dwell_s=None, steps=2)
    previous = copy.deepcopy(case); previous['factor'] = .0625
    previous['spec']['refinement'] *= 2
    for k in new.s.factory.SCALED_CONTROLS:
        previous['spec']['config']['numerics'][k] *= 2
    captured = []
    original_seal = new.s.seal
    with tempfile.TemporaryDirectory(prefix='comparator_hand_', dir=proposal.parent) as folder:
        folder = Path(folder); x = folder/'coarse.npy'; y = folder/'fine.npy'
        def evidence(physical, path):
            return dict(case=copy.deepcopy(physical), logical_core_id='hand_case', observation=copy.deepcopy(observation),
                        paths=[path], evidence_files={}, final_sha256='hand_fixture', retirement_sha256='hand_fixture')
        np.save(x, rows([H*.5, H])); np.save(y, rows([H*.25, H*.5, H*.75, H]))
        first, second = evidence(previous, x), evidence(case, y)
        # Capture assembler outputs in memory: hand fixtures are never sealed as admitted raw trajectories.
        new.s.seal = lambda path, body: captured.append(body)
        try:
            result = new.compare(first, second, folder/'never_written')
            checks['third_level_identical_path_pass'] = result['passed'] and result['new_transport_steps'] == 0
            checks['unequal_sampling_same_metrics'] = all(result['full_path_gates']['metrics'][k] == 0.
                for k in ('whole_position_over_b_max','whole_axis_vector_norm_max','endpoint_q_over_U_max','mean_L1_q_over_U_max'))
            coarse = copy.deepcopy(first); fine = copy.deepcopy(second)
            coarse['case']['factor'] = .125; fine['case']['factor'] = .0625
            checks['original_adjacent_domain_preserved'] = new.compare(coarse, fine, folder/'never_written')['passed']
            bad = copy.deepcopy(first); bad['case']['factor'] = .125
            reject('skipped_refinement_rejected', lambda: new.compare(bad, second, folder/'never_written'))
            bad = copy.deepcopy(second); bad['case']['factor'] = .015625
            reject('undeclared_finer_level_rejected', lambda: new.compare(first, bad, folder/'never_written'))
            bad = copy.deepcopy(second); bad['case']['spec']['config']['friction_coefficient'] += .01
            reject('changed_physics_rejected', lambda: new.compare(first, bad, folder/'never_written'))
            bad = copy.deepcopy(second); bad['case']['spec']['horizon_s'] *= .5
            reject('changed_exposure_rejected', lambda: new.compare(first, bad, folder/'never_written'))
            bad = copy.deepcopy(second); bad['case']['spec']['config']['numerics']['max_dt_s'] *= 1.01
            reject('nonexact_halving_rejected', lambda: new.compare(first, bad, folder/'never_written'))
            np.save(y, rows([H*.25, H*.5, H*.75, H], dq=.006*U))
            result = new.compare(first, second, folder/'never_written')
            checks['unchanged_velocity_gates_reject'] = (not result['passed'] and
                not result['full_path_gates']['checks']['endpoint_q_over_U_max'] and
                not result['full_path_gates']['checks']['mean_L1_q_over_U_max'])
            np.save(y, rows([H*.25, H*.5, H*.75, H], dx=.03*radius))
            result = new.compare(first, second, folder/'never_written')
            checks['unchanged_position_gate_rejects'] = not result['full_path_gates']['checks']['whole_position_over_b_max']
            np.save(y, rows([H*.25, H*.5]))
            reject('truncated_path_rejected', lambda: new.compare(first, second, folder/'never_written'))
            checks['no_fixture_admission_written'] = not (folder/'never_written').exists()
        finally:
            new.s.seal = original_seal
    new.api.require(all(checks.values()), 'All comparator controls pass')
    sources = {str(p.resolve()):new.s.sha(p) for p in (Path(__file__),Path(old.__file__),Path(new.__file__))}
    sources.update(new.SOURCE_FILES)
    new.s.seal(destination, dict(passed=True, new_transport_steps=0, checks=checks, source_files=sources,
        proposal_sha256=new.s.sha(proposal), transport_dispatch_authorized=False,
        scope='Comparator preparation only; hand paths do not replace full raw authentication or admit any fibre trajectory.',
        utc=new.s.utc()))
    print(json.dumps(dict(passed=True, controls=len(checks), new_transport_steps=0,
                         result_sha256=new.s.sha(destination/'results.json'))))


if __name__ == '__main__':
    run()
