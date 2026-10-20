"""Zero-advancement localization before the authenticated common-state seed."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import localize_temporal_error_v1 as analysis
import interpret_local_replay_v1 as replay
s = analysis.s


def main():
    s.environment()
    checks = analysis.controls()
    local = s.fields.sealed(replay.r.OUT/'interpretation_01/results.json')
    assert local['passed'] and not local['original_full_path_admission']
    end = local['common_state_local_metrics']['common_start_s']
    pairs = [
        ('temporal_pairs_20261014/p1_i0_rigid_prolate_ar4_u0p5',
         'p1_i0_fibre_u0p5_20261014', 'p1_i0_fibre_u0p5_fine_20261014'),
        ('temporal_pairs_20261015/p1_i0_rigid_prolate_ar4_u0p5_finer',
         'p1_i0_fibre_u0p5_fine_20261014', 'p1_i0_fibre_u0p5_accuracy_recovery_20261014')]
    inputs = {}; results = []
    for relative, first, second in pairs:
        result = s.ROOT/'paper1_evaluations'/relative/'results.json'
        receipt = s.fields.sealed(result)
        assert not receipt['passed'] and receipt['original_gate_values'] == s.q.job.policy.GATES
        s.api.verify_mapping(receipt['source_files'])
        s.api.verify_mapping(receipt['evidence_files'])
        inputs[str(result)] = s.sha(result)
        design = s.ROOT/'paper1_designs'/first/'physical_cases_01.json'
        spec = s.read(design)['cases'][0]['spec']; state = spec['initial_state']
        initial = np.array([0., *state['position_m'], *state['orientation'], *state['velocity_generalized']])
        def blocks(name):
            previous = initial.copy()
            for path in sorted((s.ROOT/'paper1_runs'/name/'records').glob('production_*/trace.npy')):
                assert str(path) in receipt['path_artifacts'] and s.sha(path) == receipt['path_artifacts'][str(path)]
                inputs[str(path)] = s.sha(path)
                rows = np.load(path, mmap_mode='r', allow_pickle=False)
                if rows[-1, 0] < end:
                    yield rows
                    previous = rows[-1].copy()
                else:
                    _, clipped = replay.clip(rows, previous, previous[0], end)
                    yield clipped
                    return
            raise ValueError('Missing exact prefix coverage')
        diagnosis = analysis.localize(blocks(first), blocks(second), initial, end,
            spec['config']['prolate_semiaxes_m'][1], spec['config']['target_mean_interstitial_velocity_m_s'], bin_count=75)
        selected = [b for b in diagnosis['bins'] if b['stop_s'] > .14 and b['start_s'] < .24]
        results.append(dict(source_roots=[first, second], prefix_diagnosis=diagnosis,
                            transition_region_bins=selected))
        print(first, second, 'PREFIX', diagnosis['mean_L1_q_over_U_max'], flush=True)
        for b in selected:
            print('BIN', b['start_s'], b['stop_s'], b['mean_q_error_over_U'], flush=True)
    target = s.ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/early_divergence_01'
    s.seal(target, dict(passed=True, new_transport_steps=0, new_contact_solver_calls=0,
        core_case_admission=False, original_accuracy_gate_changes=[], end_s=end,
        binning='75 equal fixed physical-duration bins from0 to the already selected seed time; diagnostic only, not new acceptance gates.',
        region_selection='0.14–0.24s brackets the first coarse20-bin region where halving no longer halves error; selected before finer-bin inspection.',
        pairs=results, controls=checks, inputs=inputs,
        source_files={str(Path(__file__).resolve()):s.sha(Path(__file__)),
                      str(Path(analysis.__file__).resolve()):s.sha(analysis.__file__),
                      str(Path(replay.__file__).resolve()):s.sha(replay.__file__)}, utc=s.utc()))
    print('EARLY_DIVERGENCE_SEALED', s.sha(target/'results.json'))


if __name__ == '__main__':
    main()
