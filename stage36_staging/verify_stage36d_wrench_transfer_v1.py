"""CPU-only manufactured wrench tests and read-only engine-source audit."""
import argparse
import hashlib
import io
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

from wrench_transfer_v1 import AttachmentMap, wrench, power_W
from verify_stage36b_release_accounting_v1 import AccountingTests
from verify_stage36c_fibre_volume_accounting_v1 import GeometryTests

ROOT = Path(r'C:\MATDEM_MICROPLASTIC')
STAGING = ROOT/'stage36_staging'
EXTERNAL = Path(r'C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration')
PARENT = ROOT/'stage36_evaluations/stage36c_fibre_volume_accounting_20260906/verification_01/verification.json'
DESIGN = ROOT/'stage36_designs/stage36d_single_body_force_torque_20260906/BENCHMARK_CONTRACT.md'


def fixture():
    nodes = np.array([[-.001, 0, 0], [.001, 0, 0], [.001, .001, 0]])
    samples = np.array([[0, .0002, 0], [.001, .0005, .0001]])
    mapping = AttachmentMap(nodes, samples, [[0, 1], [1, 2]], [.5, .5], accepts_nodal_couples=True)
    f = np.array([[0, 0, 1e-9], [2e-9, -1e-9, .5e-9]])
    c = np.array([[.2e-12, 0, 0], [0, .3e-12, 0]])
    return mapping, f, c


def manual_wrench(x, f, c, origin):
    force, torque = [0., 0., 0.], [0., 0., 0.]
    for point, load, couple in zip(x, f, c):
        a, b, d = (point-origin).tolist()
        fx, fy, fz = load.tolist()
        moment = [b*fz-d*fy, d*fx-a*fz, a*fy-b*fx]
        for j in range(3):
            force[j] += load[j]
            torque[j] += moment[j]+couple[j]
    return np.array(force), np.array(torque)


class WrenchTests(unittest.TestCase):
    def close(self, actual, expected, scale):
        self.assertLessEqual(float(np.max(np.abs(np.asarray(actual)-expected)))/scale, 1e-12)

    def test_01_zero_load(self):
        m, f, c = fixture()
        result = m.transfer(f*0, c*0)
        self.close(result.forces_N, 0, 1e-9)
        self.close(result.couples_Nm, 0, 1e-12)

    def test_02_known_lever_arm(self):
        got = wrench([[0, .0002, 0]], [[0, 0, 1e-9]], [[0, 0, 0]], [0, 0, 0])
        self.close(got[1], [2e-13, 0, 0], 1e-12)

    def test_03_pure_axial_couple_requires_rotations(self):
        m = AttachmentMap([[-.001, 0, 0], [.001, 0, 0]], [[0, 0, 0]], [[0, 1]], [.5], accepts_nodal_couples=True)
        result = m.transfer([[0, 0, 0]], [[1e-12, 0, 0]])
        self.close(result.forces_N, 0, 1e-9)
        self.close(result.couples_Nm, [[.5e-12, 0, 0], [.5e-12, 0, 0]], 1e-12)

    def test_04_force_and_torque_match_independent_sum(self):
        m, f, c = fixture()
        result = m.transfer(f, c)
        origin = np.array([.0001, -.0003, .0002])
        expected = manual_wrench(m.samples_m, f, c, origin)
        got = wrench(m.nodes_m, result.forces_N, result.couples_Nm, origin)
        self.close(got[0], expected[0], 1e-9)
        self.close(got[1], expected[1], 1e-12)

    def test_05_origin_translation(self):
        m, f, c = fixture()
        delta = np.array([.003, -.002, .001])
        old_f, old_t = wrench(m.samples_m, f, c, [0, 0, 0])
        new_f, new_t = wrench(m.samples_m, f, c, delta)
        self.close(new_f, old_f, 1e-9)
        self.close(new_t, old_t-np.cross(delta, old_f), 1e-12)

    def test_06_rotation_covariance(self):
        m, f, c = fixture()
        r = np.array([[0., -1, 0], [0, 0, -1], [1, 0, 0]])
        posed = AttachmentMap(m.nodes_m@r.T, m.samples_m@r.T, m.host_pairs, m.weights[:, 1], accepts_nodal_couples=True)
        a, b = m.transfer(f, c), posed.transfer(f@r.T, c@r.T)
        self.close(b.forces_N, a.forces_N@r.T, 1e-9)
        self.close(b.couples_Nm, a.couples_Nm@r.T, 1e-12)

    def test_07_translation_invariance(self):
        m, f, c = fixture()
        delta = np.array([.003, .002, -.004])
        posed = AttachmentMap(m.nodes_m+delta, m.samples_m+delta, m.host_pairs, m.weights[:, 1], accepts_nodal_couples=True)
        a, b = m.transfer(f, c), posed.transfer(f, c)
        self.close(b.forces_N, a.forces_N, 1e-9)
        self.close(b.couples_Nm, a.couples_Nm, 1e-12)

    def test_08_action_reaction(self):
        m, f, c = fixture()
        a, b = m.transfer(f, c), m.transfer(-f, -c)
        self.close(a.forces_N+b.forces_N, 0, 1e-9)
        self.close(a.couples_Nm+b.couples_Nm, 0, 1e-12)

    def test_09_nonuniform_power_conjugacy(self):
        m, f, c = fixture()
        v = np.array([[.01, -.02, .03], [0, .03, .01], [.02, 0, -.01]])
        omega = np.array([[1, 2, 3], [3, -1, 2], [-2, 0, 1.]])
        sv, sw = m.sample_velocities(v, omega)
        result = m.transfer(f, c)
        self.close(power_W(result.forces_N, result.couples_Nm, v, omega), power_W(f, c, sv, sw), 1e-12)

    def test_10_rigid_velocity_reproduction(self):
        m, _, _ = fixture()
        u, omega = np.array([.01, .02, -.01]), np.array([1., -2, 3])
        v = u+np.cross(omega, m.nodes_m)
        sv, sw = m.sample_velocities(v, np.tile(omega, (len(v), 1)))
        self.close(sv, u+np.cross(omega, m.samples_m), .01)
        self.close(sw, np.tile(omega, (len(sv), 1)), 1)

    def test_11_superposition(self):
        m, f, c = fixture()
        a, b, total = m.transfer(f, c), m.transfer(-2*f, 3*c), m.transfer(-f, 4*c)
        self.close(a.forces_N+b.forces_N, total.forces_N, 1e-9)
        self.close(a.couples_Nm+b.couples_Nm, total.couples_Nm, 1e-12)

    def test_12_shared_node_accumulation(self):
        m, f, c = fixture()
        result = m.transfer(f, c)
        self.close(result.forces_N[1], .5*(f[0]+f[1]), 1e-9)

    def test_13_length_force_rescaling(self):
        m, f, c = fixture()
        scaled = AttachmentMap(1000*m.nodes_m, 1000*m.samples_m, m.host_pairs, m.weights[:, 1], accepts_nodal_couples=True)
        a, b = m.transfer(f, c), scaled.transfer(1e6*f, 1e9*c)
        self.close(b.forces_N, 1e6*a.forces_N, 1e-3)
        self.close(b.couples_Nm, 1e9*a.couples_Nm, 1e-3)

    def test_14_random_conservation(self):
        rng = np.random.default_rng(3604)
        for _ in range(30):
            nodes, samples = rng.normal(size=(5, 3))*1e-3, rng.normal(size=(20, 3))*1e-3
            pairs = np.column_stack((np.arange(20)%4, np.arange(20)%4+1))
            m = AttachmentMap(nodes, samples, pairs, rng.random(20), accepts_nodal_couples=True)
            f, c = rng.normal(size=(20, 3))*1e-9, rng.normal(size=(20, 3))*1e-12
            result = m.transfer(f, c)
            a, b = manual_wrench(samples, f, c, np.zeros(3)), wrench(nodes, result.forces_N, result.couples_Nm, [0, 0, 0])
            self.close(a[0], b[0], 1e-9)
            self.close(a[1], b[1], 1e-12)
            v, omega = rng.normal(size=(5, 3))*.01, rng.normal(size=(5, 3))
            sv, sw = m.sample_velocities(v, omega)
            self.close(power_W(f, c, sv, sw), power_W(result.forces_N, result.couples_Nm, v, omega), 1e-12)

    def test_15_reject_force_only_receiver(self):
        with self.assertRaises(ValueError):
            AttachmentMap([[-1, 0, 0], [1, 0, 0]], [[0, 0, 0]], [[0, 1]], [.5], accepts_nodal_couples=False)

    def test_16_bad_weights(self):
        for t in [-.1, 1.1, float('nan'), True]:
            with self.subTest(t=t), self.assertRaises(ValueError):
                AttachmentMap([[-1, 0, 0], [1, 0, 0]], [[0, 0, 0]], [[0, 1]], [t], accepts_nodal_couples=True)

    def test_17_bad_topology(self):
        for pair in [[0, 0], [-1, 1], [0, 2], [0., 1.]]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                AttachmentMap([[-1, 0, 0], [1, 0, 0]], [[0, 0, 0]], [pair], [.5], accepts_nodal_couples=True)
        with self.assertRaises(ValueError):
            AttachmentMap([[0, 0, 0], [0, 0, 0]], [[0, 0, 0]], [[0, 1]], [.5], accepts_nodal_couples=True)

    def test_18_bad_loads(self):
        m, f, c = fixture()
        for bad in [np.full_like(f, np.nan), np.full_like(f, np.inf), f[:1], f.astype(complex), np.ones(f.shape, dtype=bool)]:
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                m.transfer(bad, c)
        with self.assertRaises(ValueError):
            m.transfer(f, c[:1])

    def test_19_overflow(self):
        with self.assertRaises(ValueError):
            wrench([[1e300, 0, 0]], [[0, 1e300, 0]], [[0, 0, 0]], [0, 0, 0])

    def test_20_zero_net_force_nonzero_torque(self):
        m = AttachmentMap([[-.001, 0, 0], [.001, 0, 0]], [[-.001, 0, 0], [.001, 0, 0]], [[0, 1], [0, 1]], [0, 1], accepts_nodal_couples=True)
        result = m.transfer([[0, -1e-9, 0], [0, 1e-9, 0]], np.zeros((2, 3)))
        f, t = wrench(m.nodes_m, result.forces_N, result.couples_Nm, [0, 0, 0])
        self.close(f, 0, 1e-9)
        self.close(t, [0, 0, 2e-12], 1e-12)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_parent(path, verified=None):
    verified = {} if verified is None else verified
    data = json.loads(path.read_text())
    if data.get('passed') is not True:
        raise ValueError('parent not passed: '+str(path))
    for group in ('source_hashes', 'artifact_hashes'):
        for name, expected in data[group].items():
            p = Path(name)
            p = p if p.is_absolute() else ROOT/p
            p = p.resolve()
            if sha(p) != expected:
                raise ValueError('parent binding mismatch: '+str(p))
            if str(p) not in verified:
                verified[str(p)] = expected
                if p.name == 'verification.json':
                    check_parent(p, verified)
    return verified


def source_audit():
    config_path = ROOT/'stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json'
    cfg = json.loads(config_path.read_text())
    lineage = {}
    for key in ('cuda_source', 'stage13_runner', 'stage13_qualification', 'stage13_execution_manifest'):
        entry = cfg['lineage'][key]
        if sha(entry['path']) != entry['sha256']:
            raise ValueError('engine lineage mismatch: '+key)
        lineage[key] = entry
    snippets = [
        (ROOT/'stage31_staging/run_stage31f_selected_replicated_cpd4_gpu_v1.py', [(18, 21), (96, 108)]),
        (EXTERNAL/'scripts/stage17_relaxed_fibre_gpu_lbm_run.py', [(213, 239), (331, 348)]),
        (EXTERNAL/'scripts/stage13a_gpu_lbm_sphere_drag_run.py', [(794, 815), (1004, 1047), (2228, 2294), (2303, 2328)]),
        (EXTERNAL/'src/stage13a_gpu_lbm_d3q19_arbitrary_solid.cu', [(1, 8), (498, 511), (535, 579)]),
        (ROOT/'stage31_staging/run_stage31c_replicated_nested_mechanics_v1.py', [(83, 91), (175, 192)]),
        (ROOT/'native_matdem/native_matdem_run_coupled_permeability.m', [(56, 68), (160, 176)]),
        (ROOT/'config/native_matdem_hydromechanical_config.m', [(1, 7), (69, 80)])]
    evidence = []
    for path, ranges in snippets:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        evidence.append({'path': str(path), 'sha256': sha(path), 'excerpts': [
            {'first_line': a, 'last_line': b, 'text': '\n'.join(f'{i}: {lines[i-1]}' for i in range(a, b+1))}
            for a, b in ranges]})
    return {'scope': 'read-only selected local call-path audit, not exhaustive engine capability certification',
            'config_path': str(config_path), 'config_sha256': sha(config_path),
            'frozen_stage31f_lineage_checks': lineage, 'evidence': evidence,
            'findings': {
                'static_link_force_and_moment_reconstruction_present': True,
                'aggregate_solid_force_and_torque_output_present': True,
                'per_fibre_body_id_export_in_audited_call_path': False,
                'wall_velocity_argument_in_audited_cuda_step': False,
                'moving_mask_repopulation_in_audited_session': False,
                'open_streamwise_outlet_in_audited_kernel': False,
                'yade_mechanics_uses_prescribed_tip_force': True,
                'native_matdem_current_config_fixed_sphere_placeholder': True,
                'engine_nodal_torque_application_tested_this_run': False},
            'decision': 'reuse immutable static LBM as a reference candidate; separate adapter and moving-boundary verification required',
            'software_installed_or_engine_started': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = datetime.now(timezone.utc).isoformat()
    parent_checks = check_parent(PARENT)
    audit = source_audit()
    (output/'engine_source_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                                for cls in (AccountingTests, GeometryTests, WrenchTests))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    m, f, c = fixture()
    transfer = m.transfer(f, c)
    expected = manual_wrench(m.samples_m, f, c, np.zeros(3))
    got = wrench(m.nodes_m, transfer.forces_N, transfer.couples_Nm, [0, 0, 0])
    v = np.array([[.01, -.02, .03], [0, .03, .01], [.02, 0, -.01]])
    omega = np.array([[1, 2, 3], [3, -1, 2], [-2, 0, 1.]])
    sv, sw = m.sample_velocities(v, omega)
    p_source, p_nodes = power_W(f, c, sv, sw), power_W(transfer.forces_N, transfer.couples_Nm, v, omega)
    example = {'nodes_m': m.nodes_m.tolist(), 'samples_m': m.samples_m.tolist(),
               'source_forces_N': f.tolist(), 'source_couples_Nm': c.tolist(),
               'node_forces_N': transfer.forces_N.tolist(), 'node_couples_Nm': transfer.couples_Nm.tolist(),
               'origin_m': [0, 0, 0], 'source_force_N': expected[0].tolist(), 'source_torque_Nm': expected[1].tolist(),
               'mapped_force_N': got[0].tolist(), 'mapped_torque_Nm': got[1].tolist(),
               'source_power_W': p_source, 'node_power_W': p_nodes,
               'scaled_force_error': float(np.max(np.abs(got[0]-expected[0]))/1e-9),
               'scaled_torque_error': float(np.max(np.abs(got[1]-expected[1]))/1e-12),
               'scaled_power_error': abs(p_source-p_nodes)/1e-12}
    (output/'manufactured_transfer.json').write_text(json.dumps(example, indent=2), encoding='utf-8')
    source_paths = [Path(__file__).resolve(), STAGING/'wrench_transfer_v1.py',
                    STAGING/'STAGE36D_WRENCH_INTERFACE_CONTRACT.md', DESIGN, PARENT]
    metrics_passed = all(example[k] <= 1e-12 for k in ('scaled_force_error', 'scaled_torque_error', 'scaled_power_error'))
    report = {'passed': result.wasSuccessful() and metrics_passed, 'scope': 'manufactured wrench transfer, not hydrodynamic benchmark',
              'tests_run': result.testsRun, 'regression_tests': 41, 'new_wrench_tests': 20,
              'failures': len(result.failures), 'errors': len(result.errors), 'started_utc': start,
              'finished_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(), 'numpy': np.__version__,
              'executable': sys.executable, 'cwd': str(Path.cwd()), 'command_argv': sys.argv,
              'parent_binding_checks': parent_checks,
              'source_hashes': {str(p): sha(p) for p in source_paths},
              'artifact_hashes': {str(output/n): sha(output/n) for n in ['tests.txt', 'manufactured_transfer.json', 'engine_source_audit.json']},
              'force_torque_mapping_unit_verified': result.wasSuccessful() and metrics_passed,
              'fluid_solver_force_validated': False, 'engine_adapter_integrated': False,
              'transport_physics_verified': False, 'physics_simulations_started': 0, 'soil_pilot_execution_authorized': False}
    (output/'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('passed', 'tests_run', 'failures', 'errors', 'physics_simulations_started')}, indent=2))
    print(json.dumps(example, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
