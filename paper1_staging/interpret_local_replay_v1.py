"""Read-only same-clock interpretation of the completed common-state diagnostic."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_local_replay_v1 as evaluator
r = evaluator.run
s = r.s


def clip(rows, initial, start, stop):
    """Original linear nodal pose and right-end accepted interval velocity."""
    nodes = np.vstack([initial, rows])
    assert nodes[0, 0] <= start < stop <= nodes[-1, 0]
    def node(t):
        j = int(np.searchsorted(nodes[:, 0], t, side='left'))
        if nodes[j, 0] == t:
            return nodes[j].copy()
        assert j > 0
        out = nodes[j].copy()
        f = (t - nodes[j-1, 0]) / (nodes[j, 0] - nodes[j-1, 0])
        out[0] = t
        out[1:7] = nodes[j-1, 1:7] + f * (nodes[j, 1:7] - nodes[j-1, 1:7])
        return out
    inside = rows[(rows[:, 0] > start) & (rows[:, 0] < stop)]
    return node(start), np.vstack([inside, node(stop)])


def main():
    s.environment()
    audit_path = r.OUT/'evaluation_01/results.json'
    audit = s.fields.sealed(audit_path)
    assert audit['passed'] and not audit['original_full_path_admission']
    s.api.verify_mapping(audit['artifacts'])
    s.api.verify_mapping(audit['source_files'])
    pair_path = r.ROOT/'paper1_evaluations/temporal_pairs_20261015/p1_i0_rigid_prolate_ar4_u0p5_finer/results.json'
    pair = s.fields.sealed(pair_path)
    assert not pair['passed'] and pair['original_gate_values'] == s.q.job.policy.GATES
    start = audit['local_metrics']['common_start_s']
    stop = audit['local_metrics']['common_stop_s']
    inputs = {str(audit_path):r.sha(audit_path), str(pair_path):r.sha(pair_path)}
    old = []
    initial = []
    for name in ('p1_i0_fibre_u0p5_fine_20261014', 'p1_i0_fibre_u0p5_accuracy_recovery_20261014'):
        design = r.ROOT/'paper1_designs'/name/'physical_cases_01.json'
        spec = r.read(design)['cases'][0]['spec']
        seed = spec['initial_state']
        origin = np.array([0., *seed['position_m'], *seed['orientation'], *seed['velocity_generalized']])
        selected = []
        previous = origin
        for path in sorted((r.ROOT/'paper1_runs'/name/'records').glob('production_*/trace.npy')):
            rows = np.load(path, mmap_mode='r', allow_pickle=False)
            if rows[-1, 0] < start:
                previous = rows[-1].copy()
                continue
            assert str(path) in pair['path_artifacts'] and r.sha(path) == pair['path_artifacts'][str(path)]
            inputs[str(path)] = r.sha(path)
            selected.append(np.array(rows))
            if rows[-1, 0] >= stop:
                break
        a, b = clip(np.concatenate(selected), previous, start, stop)
        initial.append(a); old.append(b)
    # Clipping cannot manufacture velocity agreement: constant accepted
    # intervals retain their original value and their exact physical duration.
    x = np.zeros((2, 13)); x[:, 0] = [.4, .6]; x[:, 4] = 1.; x[:, 7] = [2., 4.]
    z = np.zeros(13); z[4] = 1.
    c, d = clip(x, z, .2, .5)
    assert c[0] == .2 and d[-1, 0] == .5 and list(d[:, 7]) == [2., 4.]
    assert np.array_equal(clip(x, z, .4, .6)[1], x[1:])
    final = s.fields.sealed(r.OUT/'final_disposition_01/results.json')
    local = np.concatenate([np.load(r.OUT/'records'/label/'trace.npy', allow_pickle=False)
                            for label in final['branches'][0]['labels']])
    # The changed local stop truncates the last numerical interval only.
    assert len(old[0]) == len(local) and np.array_equal(old[0][:-1], local[:-1])
    spec = r.read(r.PHYSICAL)['cases'][0]['spec']
    cfg = spec['config']
    metrics = s.q.job.path_metrics.metrics([old[0]], [old[1]], initial[0], initial[1], stop, stop,
        cfg['prolate_semiaxes_m'][1], cfg['target_mean_interstitial_velocity_m_s'])
    r.seal(r.OUT/'interpretation_01', dict(passed=True, new_transport_steps=0,
        exact_archived_same_factor_preterminal_rows=len(local)-1,
        terminal_interval_separately_truncated=True, original_pair_same_interval_metrics=metrics,
        common_state_local_metrics=audit['local_metrics'],
        inference='Small local differences from a common state do not reproduce the accumulated full-path failure in this interval; cause outside this interval is not identified.',
        original_full_path_admission=False, successor_dispatch_authorized=False,
        controls=['accepted_interval_velocity_preserved_on_clip', 'exact_node_clip', 'same_factor_archived_preterminal_rows_exact'],
        source_files={str(Path(__file__).resolve()):r.sha(Path(__file__)), **audit['source_files']},
        inputs=inputs, utc=s.utc()))
    print('LOCAL_INTERPRETATION', r.sha(r.OUT/'interpretation_01/results.json'), metrics)


if __name__ == '__main__':
    main()
