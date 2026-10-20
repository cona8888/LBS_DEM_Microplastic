"""Bounded CPU geometry fixtures; no physics engine is imported or launched."""
import argparse
import hashlib
import io
import json
import math
import platform
import unittest
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

from fibre_volume_accounting_v1 import make_cloud, rigid, fractions, crossing
from release_accounting_v1 import Body, fraction_left
from verify_stage36b_release_accounting_v1 import AccountingTests

ROOT = Path(r'C:\MATDEM_MICROPLASTIC')
STAGING = ROOT/'stage36_staging'
PARENT = ROOT/'stage36_evaluations/stage36b_release_accounting_20260906/verification_01/verification.json'
I = np.eye(3)
FLIP = np.diag([-1., -1., 1.])
STRAIGHT = [[-1., 0, 0], [1., 0, 0]]
BENT = [[-1., 0, 0], [0., 0, 0], [0., 1., 0]]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def refinement():
    body = Body('analytic', 1., 2., .5)
    exact_volume = math.pi*.5**2*2 + 4*math.pi*.5**3/3
    angle = math.pi/5
    r = np.array([[math.cos(angle), -math.sin(angle), 0],
                  [math.sin(angle), math.cos(angle), 0], [0, 0, 1]])
    rows = []
    for cpd in (16, 32, 64):
        straight = make_cloud(STRAIGHT, .5, cpd)
        bent = make_cloud(BENT, .5, cpd)
        errors = [abs(np.mean(straight.samples[:, 0] <= p)-fraction_left(body, p))
                  for p in [-1.375, -.75, 0, .5, .9, 1.375]]
        rows.append({'cpd': cpd, 'straight_samples': len(straight.samples),
                     'straight_raw_volume': straight.raw_volume,
                     'straight_volume_relative_error': abs(straight.raw_volume/exact_volume-1),
                     'straight_max_fraction_error': float(max(errors)),
                     'oblique_half_fraction_error': abs(fractions(straight.categories(r, [0, 0, 0], -5, 0))['downstream']-.5),
                     'bent_samples': len(bent.samples), 'bent_raw_volume': bent.raw_volume,
                     'bent_outlet_fractions': [fractions(bent.categories(I, [0, 0, 0], -5, p))['downstream']
                                               for p in [0, .25, .625]]})
    rows[-1]['bent_last_refinement_volume_shift'] = abs(rows[-1]['bent_raw_volume']/rows[-2]['bent_raw_volume']-1)
    rows[-1]['bent_last_refinement_max_fraction_shift'] = max(abs(a-b) for a, b in zip(rows[-1]['bent_outlet_fractions'], rows[-2]['bent_outlet_fractions']))
    return rows


class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cloud = make_cloud(STRAIGHT, .5, 16)
        cls.bent = make_cloud(BENT, .5, 16)

    def test_01_collinear_subdivision(self):
        other = make_cloud([[-1, 0, 0], [0, 0, 0], [1, 0, 0]], .5, 16)
        np.testing.assert_array_equal(self.cloud.samples, other.samples)

    def test_02_retraced_union_not_double_counted(self):
        other = make_cloud([[-1, 0, 0], [1, 0, 0], [-1, 0, 0]], .5, 16)
        np.testing.assert_array_equal(self.cloud.samples, other.samples)

    def test_03_rigid_distance_preserved(self):
        posed = rigid(self.bent.samples, FLIP, [2, 3, 4])
        np.testing.assert_allclose(np.linalg.norm(posed-posed[0], axis=1),
                                   np.linalg.norm(self.bent.samples-self.bent.samples[0], axis=1), atol=1e-14)

    def test_04_zero_motion(self):
        c = self.bent.categories(I, [0, 0, 0], -5, 5)
        got = crossing(c, c, 1e-9)
        self.assertEqual(got['outlet_outward_kg'], 0)
        self.assertEqual(got['outlet_return_kg'], 0)
        self.assertEqual(got['fractions']['inside'], 1)

    def test_05_rotation_simultaneous_out_and_return(self):
        a = self.cloud.categories(I, [5, 0, 0], -5, 5)
        b = self.cloud.categories(FLIP, [5, 0, 0], -5, 5)
        got = crossing(a, b, 1e-9)
        self.assertAlmostEqual(got['outlet_outward_kg']/1e-9, .5)
        self.assertAlmostEqual(got['outlet_return_kg']/1e-9, .5)
        self.assertEqual(fractions(a), fractions(b))

    def test_06_complete_bounds_not_sample_bounds(self):
        # Last sample is out but the unsampled spherical-cap tail remains inside.
        shift = 6.5-self.cloud.spacing/4
        self.assertEqual(fractions(self.cloud.categories(I, [shift, 0, 0], -5, 5))['downstream'], 1)
        self.assertFalse(self.cloud.full_exit(I, [shift, 0, 0], 5))
        self.assertTrue(self.cloud.full_exit(I, [6.5, 0, 0], 5))

    def test_07_upstream_crossing(self):
        a = self.bent.categories(I, [0, 0, 0], -5, 5)
        b = self.bent.categories(I, [-8, 0, 0], -5, 5)
        got = crossing(a, b, 1e-9)
        self.assertAlmostEqual(got['inlet_outward_kg']/1e-9, 1)
        self.assertEqual(got['fractions']['inside'], 0)

    def test_08_bad_rotations(self):
        for r in [2*I, np.diag([-1, 1, 1]), np.zeros((3, 3)), np.full((3, 3), np.nan)]:
            with self.subTest(r=r), self.assertRaises(ValueError):
                rigid(STRAIGHT, r, [0, 0, 0])

    def test_09_invalid_centreline(self):
        for n in [[[0, 0, 0]], [[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [float('nan'), 0, 0]]]:
            with self.subTest(n=n), self.assertRaises(ValueError):
                make_cloud(n, .5, 16)

    def test_10_bad_discretization(self):
        for r, c in [(0, 16), (-1, 16), (float('inf'), 16), (.5, True), (.5, 1), (.5, 3.5)]:
            with self.subTest(r=r, c=c), self.assertRaises(ValueError):
                make_cloud(STRAIGHT, r, c)

    def test_11_resource_gate(self):
        with self.assertRaises(ValueError):
            make_cloud(STRAIGHT, .5, 128, max_candidates=100)

    def test_12_invalid_categories_or_material_size(self):
        for a, b in [([0], [0, 0]), ([2], [0]), ([], []), ([np.nan], [0])]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                crossing(a, b, 1)

    def test_13_invalid_mass(self):
        for m in [0, -1, True, float('inf')]:
            with self.subTest(m=m), self.assertRaises(ValueError):
                crossing([0], [1], m)

    def test_14_invalid_boundaries_or_translation(self):
        for a, b in [(1, 1), (2, 1), (0, float('nan'))]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                self.cloud.categories(I, [0, 0, 0], a, b)
        with self.assertRaises(ValueError):
            self.cloud.categories(I, [0, float('nan'), 0], -5, 5)

    def test_15_random_endpoint_closure(self):
        rng = np.random.default_rng(3603)
        for _ in range(40):
            a, b = rng.integers(-1, 2, (2, 300))
            got = crossing(a, b, 1e-9)
            for key, value in got.items():
                if 'residual' in key:
                    self.assertLessEqual(abs(value), 1e-12)

    def test_16_sample_array_readonly(self):
        with self.assertRaises(ValueError):
            self.cloud.samples[0, 0] = 99


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    parent = json.loads(PARENT.read_text())
    checks = {path: sha(path) == value for group in ('source_hashes', 'artifact_hashes')
              for path, value in parent[group].items()}
    if parent.get('passed') is not True or not all(checks.values()):
        raise RuntimeError('Stage36B parent integrity failure')
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(AccountingTests),
                                unittest.defaultTestLoader.loadTestsFromTestCase(GeometryTests)])
    text = io.StringIO()
    result = unittest.TextTestRunner(stream=text, verbosity=2).run(suite)
    (args.output/'tests.txt').write_text(text.getvalue(), encoding='utf-8')
    rows = refinement()
    finest = rows[-1]
    gates = {
        'axial_volume_error_le_0p01': finest['straight_volume_relative_error'] <= .01,
        'axial_fraction_error_le_0p005': finest['straight_max_fraction_error'] <= .005,
        'oblique_half_error_le_0p005': finest['oblique_half_fraction_error'] <= .005,
        'bent_volume_shift_le_0p01': finest['bent_last_refinement_volume_shift'] <= .01,
        'bent_fraction_shift_le_0p005': finest['bent_last_refinement_max_fraction_shift'] <= .005}
    cloud = make_cloud(STRAIGHT, .5, 16)
    old = cloud.categories(I, [0, 0, 0], -5, 5)
    history = []
    for label, r, t in [('half_out', I, [5, 0, 0]), ('rotated_at_outlet', FLIP, [5, 0, 0]),
                        ('fully_out', FLIP, [7, 0, 0]), ('returned', I, [0, 0, 0])]:
        new = cloud.categories(r, t, -5, 5)
        history.append({'pose': label, 'full_body_exit': cloud.full_exit(r, t, 5), **crossing(old, new, 1e-9)})
        old = new
    (args.output/'manufactured_history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
    sources = [Path(__file__), STAGING/'fibre_volume_accounting_v1.py',
               STAGING/'STAGE36C_GEOMETRY_ACCOUNTING_CONTRACT.md', PARENT]
    passed = result.wasSuccessful() and all(gates.values())
    report = {'passed': passed, 'scope': 'manufactured rigid capsule-union geometry and endpoint accounting',
              'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'numpy': np.__version__, 'tests_run': result.testsRun, 'regression_tests': 25,
              'new_geometry_tests': 16, 'failures': len(result.failures), 'errors': len(result.errors),
              'refinement': rows, 'gates': gates, 'parent_binding_checks': checks,
              'source_hashes': {str(p): sha(p) for p in sources},
              'artifact_hashes': {str(args.output/n): sha(args.output/n) for n in ['tests.txt', 'manufactured_history.json']},
              'physics_simulations_started': 0, 'transport_physics_verified': False,
              'deforming_fibre_accounting_verified': False, 'soil_pilot_execution_authorized': False,
              'limitation': 'Gross crossings resolve endpoint category changes only; sample order must be preserved.'}
    (args.output/'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': passed, 'tests_run': result.testsRun, 'gates': gates, 'finest': finest}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
