"""Read-only diagnosis of rejected full paths using the original clock convention."""
from pathlib import Path
import math
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_core_v2 as comparison
s = comparison.s
api = s.api
Cursor = s.q.job.path_metrics.Cursor


def localize(blocks_a, blocks_b, initial, end, radius, speed, bin_count=20):
    a, b = Cursor(blocks_a, initial, end), Cursor(blocks_b, initial, end)
    edges = np.linspace(0., end, bin_count + 1)
    parts = [[] for _ in range(bin_count)]
    total = []; translation = []; angular_scaled = []
    thresholds = (.005, .05, .5, 5.)
    exceed = {value: [] for value in thresholds}
    left = 0.; pose = axis = peak = 0.; peak_time = None; endpoint = None
    while not (a.done or b.done):
        right = min(a.times[-1], b.times[-1])
        interior = [x.times[(x.times > left) & (x.times < right)] for x in (a, b)]
        grid = np.unique(np.r_[left, interior[0], interior[1], right])
        delta = a.interpolate_pose(grid) - b.interpolate_pose(grid)
        pose = max(pose, float(np.linalg.norm(delta[:, :3], axis=1).max()) / radius)
        axis = max(axis, float(np.linalg.norm(delta[:, 3:], axis=1).max()))
        dq = (a.interval_velocities(grid[1:]) - b.interval_velocities(grid[1:])) / speed
        error = np.linalg.norm(dq, axis=1)
        duration = np.diff(grid)
        total.append(float(np.dot(error, duration)))
        translation.append(float(np.dot(np.linalg.norm(dq[:, :3], axis=1), duration)))
        angular_scaled.append(float(np.dot(np.linalg.norm(dq[:, 3:], axis=1), duration)))
        for value in thresholds:
            exceed[value].append(float(duration[error > value].sum()))
        for i in range(bin_count):
            overlap = np.maximum(0., np.minimum(grid[1:], edges[i+1]) - np.maximum(grid[:-1], edges[i]))
            parts[i].append(float(np.dot(error, overlap)))
        index = int(np.argmax(error))
        if error[index] > peak:
            peak = float(error[index]); peak_time = float(grid[index+1])
        endpoint = dq[-1].tolist()
        left = right
        if right == a.times[-1]:
            a.load()
        if right == b.times[-1]:
            b.load()
    api.require(left == end, 'Entire exact common clock; no extrapolation or impact realignment')
    integral = math.fsum(total)
    bins = [dict(start_s=float(edges[i]), stop_s=float(edges[i+1]),
                 integrated_q_error_over_U_s=math.fsum(values),
                 mean_q_error_over_U=math.fsum(values)/(edges[i+1]-edges[i]),
                 fraction_of_total_L1=math.fsum(values)/integral if integral else 0.)
            for i, values in enumerate(parts)]
    api.require(math.isclose(math.fsum(x['integrated_q_error_over_U_s'] for x in bins), integral,
                            rel_tol=1e-12, abs_tol=1e-14), 'Time-bin partition preserves original integral')
    return dict(whole_position_over_b_max=pose, whole_axis_vector_norm_max=axis,
                endpoint_q_over_U_max=float(np.linalg.norm(endpoint)),
                mean_L1_q_over_U_max=integral/end, integrated_q_error_over_U_s=integral,
                interval_velocity_sup_over_U_diagnostic_only=peak,
                peak_interval_right_time_s_diagnostic_only=peak_time,
                endpoint_delta_q_over_U=endpoint,
                mean_translation_error_over_U=math.fsum(translation)/end,
                mean_angular_scaled_error_over_U=math.fsum(angular_scaled)/end,
                fraction_observation_above_q_threshold={str(k):math.fsum(v)/end for k,v in exceed.items()},
                bins=bins)


def controls():
    initial = [0., 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.]
    def rows(times, value):
        x = np.zeros((len(times), 13)); x[:, 0] = times; x[:, 4] = 1.; x[:, 7] = value
        return x
    a = localize([rows([.3, 1.], .02)], [rows([.1, .4, .8, 1.], 0.)], initial, 1., 1., 1.)
    assert math.isclose(a['mean_L1_q_over_U_max'], .02) and all(math.isclose(x['mean_q_error_over_U'], .02) for x in a['bins'])
    assert math.isclose(a['fraction_observation_above_q_threshold']['0.005'], 1.)
    assert a['fraction_observation_above_q_threshold']['0.05'] == 0.
    pulse = rows([.1, 1.], 0.); pulse[0, 7] = 1.
    b = localize([pulse], [rows([.2, .6, 1.], 0.)], initial, 1., 1., 1.)
    assert math.isclose(b['integrated_q_error_over_U_s'], .1)
    try:
        localize([rows([.5], 0.)], [rows([1.], 0.)], initial, 1., 1., 1.)
    except ValueError:
        pass
    else:
        raise AssertionError('Incomplete path admitted')
    return ['unequal_clock_sampling', 'hand_constant_error', 'exact_bin_partition',
            'physical_duration_thresholds', 'unshifted_pulse_integral', 'incomplete_path_rejected']


def main():
    s.environment(); checks = controls()
    destination = s.ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015'
    api.require(not destination.exists(), 'Create-only numerical-failure diagnosis')
    pairs = [
        ('temporal_pairs_20261014/p1_i0_rigid_prolate_ar4_u0p5', 'p1_i0_fibre_u0p5_20261014', 'p1_i0_fibre_u0p5_fine_20261014'),
        ('temporal_pairs_20261015/p1_i0_rigid_prolate_ar4_u0p5_finer', 'p1_i0_fibre_u0p5_fine_20261014', 'p1_i0_fibre_u0p5_accuracy_recovery_20261014')]
    results = []; inputs = {}; sources = {}
    for relative, first, second in pairs:
        path = s.ROOT/'paper1_evaluations'/relative/'results.json'
        admitted = s.fields.sealed(path)
        api.require(not admitted['passed'] and admitted['whole_start_to_terminal_paths']
                    and admitted['original_gate_values'] == s.q.job.policy.GATES, 'Original complete negative comparison')
        for key in ('source_files', 'evidence_files', 'path_artifacts'):
            api.verify_mapping(admitted[key])
        sources.update(admitted['source_files']); inputs[str(path)] = s.sha(path)
        paths = []
        for name in (first, second):
            candidates = sorted((s.ROOT/'paper1_runs'/name/'records').glob('production_*/trace.npy'))
            api.require(candidates and all(str(x) in admitted['path_artifacts'] for x in candidates), 'Only authenticated traces')
            paths.append(candidates)
        api.require(sum(map(len, paths)) == len(admitted['path_artifacts']), 'No omitted trace blocks')
        physical = s.ROOT/'paper1_designs'/first/'physical_cases_01.json'
        case = s.read(physical)['cases'][0]; spec = case['spec']; initial = spec['initial_state']
        node = [0., *initial['position_m'], *initial['orientation'], *initial['velocity_generalized']]
        def blocks(paths):
            for p in paths:
                yield np.load(p, mmap_mode='r', allow_pickle=False)
        diagnosis = localize(blocks(paths[0]), blocks(paths[1]), node, spec['horizon_s'],
                             spec['config']['prolate_semiaxes_m'][1], spec['config']['target_mean_interstitial_velocity_m_s'])
        metrics = admitted['full_path_gates']['metrics']
        for key in ('whole_position_over_b_max','whole_axis_vector_norm_max','endpoint_q_over_U_max',
                    'mean_L1_q_over_U_max','integrated_q_error_over_U_s','interval_velocity_sup_over_U_diagnostic_only'):
            api.require(math.isclose(diagnosis[key], metrics[key], rel_tol=1e-11, abs_tol=1e-13), 'Reproduce original whole-path metric: '+key)
        results.append(dict(comparison=str(path), source_roots=[first,second], diagnosis=diagnosis,
                            original_metrics_reproduced=True))
    sources[str(Path(__file__).resolve())] = s.sha(Path(__file__))
    s.seal(destination, dict(passed=True, scope='Diagnostic reconstruction only; neither rejected pair is admitted.',
           new_transport_steps=0, core_case_admission=False, controls=checks, pairs=results,
           source_files=sources, inputs=inputs, no_smoothing_or_impact_alignment=True, utc=s.utc()))
    print('NUMERICAL_FAILURE_LOCALIZED',s.sha(destination/'results.json'),flush=True)


if __name__ == '__main__':
    main()
