"""Zero-native scientific controls for the Paper1 dataset assembly helpers.

Synthetic measurements exercise contrast resolution and censoring semantics.
No dataset producer, field loader, numerical launcher or transport is invoked.
"""
from pathlib import Path
import copy
import math
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble_dataset_v1 as assembly


class FiniteContrastTests(unittest.TestCase):
    def test_direction_and_strict_feature_change_boundary(self):
        boundary = assembly.finite_contrast(0., 0., 3., 2.)
        self.assertEqual(boundary['coarse_difference'], 3.)
        self.assertEqual(boundary['fine_difference'], 2.)
        self.assertEqual(boundary['twice_sum_feature_changes'], 2.)
        self.assertFalse(boundary['resolved'])
        self.assertTrue(assembly.finite_contrast(0., 0., 3., 2.25)['resolved'])
        self.assertFalse(assembly.finite_contrast(0., 0., 3., 1.75)['resolved'])

    def test_nonzero_consistent_sign_required(self):
        for values in ((0., 0., 0., 0.), (0., 0., 0., 1.),
                       (0., 0., 1., 0.), (0., 0., 1., -1.)):
            with self.subTest(values=values):
                self.assertFalse(assembly.finite_contrast(*values)['resolved'])
        self.assertTrue(assembly.finite_contrast(0., .125, 2., 2.125)['resolved'])
        self.assertTrue(assembly.finite_contrast(2., 2.125, 0., .125)['resolved'])

    def test_both_feature_changes_contribute(self):
        row = assembly.finite_contrast(10., 10.25, 11., 11.25)
        self.assertEqual(row['coarse_difference'], 1.)
        self.assertEqual(row['fine_difference'], 1.)
        self.assertEqual(row['twice_sum_feature_changes'], 1.)
        self.assertFalse(row['resolved'])

    def test_exchange_scale_and_origin_invariance(self):
        rng = random.Random(67119)
        for _ in range(100):
            values = [rng.randint(-40, 40) / 8 for _ in range(4)]
            ac, af, bc, bf = values
            row = assembly.finite_contrast(*values)
            exchanged = assembly.finite_contrast(bc, bf, ac, af)
            self.assertEqual(exchanged['coarse_difference'], -row['coarse_difference'])
            self.assertEqual(exchanged['fine_difference'], -row['fine_difference'])
            self.assertEqual(exchanged['twice_sum_feature_changes'], row['twice_sum_feature_changes'])
            self.assertEqual(exchanged['resolved'], row['resolved'])
            for scale in (.125, 16., 1024.):
                scaled = assembly.finite_contrast(*(x * scale for x in values))
                self.assertEqual(scaled['resolved'], row['resolved'])
                for key in ('coarse_difference', 'fine_difference', 'twice_sum_feature_changes'):
                    self.assertEqual(scaled[key], row[key] * scale)
            shifted = assembly.finite_contrast(*(x + 1024. for x in values))
            self.assertEqual(shifted['resolved'], row['resolved'])
            self.assertEqual(shifted['twice_sum_feature_changes'], row['twice_sum_feature_changes'])

    def test_invalid_or_nonfinite_inputs_never_form_a_contrast(self):
        for value in (None, True, False, '1', complex(1, 0), math.nan, math.inf, -math.inf):
            for index in range(4):
                inputs = [0., .125, 2., 2.125]
                inputs[index] = value
                with self.subTest(value=value, index=index):
                    with self.assertRaises((ValueError, TypeError)):
                        assembly.finite_contrast(*inputs)

    def test_finite_inputs_with_overflowing_derived_error_are_rejected(self):
        with self.assertRaises((ValueError, TypeError)):
            assembly.finite_contrast(-1.e308, 1.e308, 0., 0.)


class ExportBoundsTests(unittest.TestCase):
    @staticmethod
    def counts(values):
        row = assembly.export_bounds(values)
        return {key: row[key] for key in ('minimum_exports', 'maximum_exports',
                'known_labels', 'unresolved_labels', 'total_labels')}

    def test_labelled_partial_bounds_preserve_unknowns(self):
        values = [True, False, None, True, None]
        before = copy.deepcopy(values)
        row = self.counts(values)
        self.assertEqual(row, dict(minimum_exports=2, maximum_exports=4,
                                  known_labels=3, unresolved_labels=2, total_labels=5))
        self.assertEqual(values, before)

    def test_empty_all_missing_and_known_negative(self):
        self.assertEqual(self.counts([]), dict(minimum_exports=0,
            maximum_exports=0, known_labels=0, unresolved_labels=0, total_labels=0))
        self.assertEqual(self.counts([None] * 10), dict(minimum_exports=0,
            maximum_exports=10, known_labels=0, unresolved_labels=10, total_labels=10))
        self.assertEqual(self.counts([False]), dict(minimum_exports=0,
            maximum_exports=0, known_labels=1, unresolved_labels=0, total_labels=1))

    def test_order_does_not_create_population_information(self):
        values = [True, False, None, True, False, None]
        expected = assembly.export_bounds(values)
        rng = random.Random(78)
        for _ in range(20):
            rng.shuffle(values)
            self.assertEqual(assembly.export_bounds(values), expected)

    def test_no_numeric_or_string_coercion_to_boolean(self):
        for value in (0, 1, 0., 1., 'False', math.nan, {}, []):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    assembly.export_bounds([True, value, None])


DISPLACEMENT = 'downstream_displacement_m'
ANGLE = 'fibre_director_angle_to_flow_rad'
FEATURES = [DISPLACEMENT, ANGLE]


def measurement(base, horizon=1.):
    """Two numerical levels, each with three labelled query targets."""
    variants = []
    for change in (0., .125):
        summary = dict(observed_stop_s=horizon, horizon_s=horizon,
            whole_body_control_volume_export=False,
            downstream_displacement_m=base + change,
            fibre_director_angle_to_flow_rad=None)
        queries = [
            dict(kind='common_pv', target_pv=.0025, time_s=.25 * horizon,
                 available=True, downstream_displacement_m=base + 1. + change,
                 fibre_director_angle_to_flow_rad=None),
            dict(kind='common_physical_time', time_s=.25, available=True,
                 downstream_displacement_m=base + 10. + change,
                 fibre_director_angle_to_flow_rad=None),
            dict(kind='common_pv', target_pv=.005, time_s=.5 * horizon,
                 available=True, downstream_displacement_m=base + 2. + change,
                 fibre_director_angle_to_flow_rad=None)]
        variants.append(dict(summary=summary, queries=queries))
    return dict(variants=variants)


def query(result, kind, target):
    found = [q for q in result['queries'] if (q['kind'], q['target']) == (kind, target)]
    if len(found) != 1:
        raise AssertionError('Expected one exact query target, got ' + repr(found))
    return found[0]


class PairContrastTests(unittest.TestCase):
    def test_full_endpoints_at_own_horizons_allow_common_dose_across_flows(self):
        a, b = measurement(0., horizon=1.), measurement(2., horizon=2.)
        before = copy.deepcopy((a, b))
        result = assembly.pair_contrasts(a, b, FEATURES)
        self.assertTrue(result['available'])
        self.assertTrue(result['summary']['available'])
        self.assertEqual(result['summary']['features'][DISPLACEMENT]['fine_difference'], 2.)
        self.assertEqual(result['endpoint_primary_export_difference'], 0)
        self.assertEqual((a, b), before)

    def test_matching_uses_exact_clock_target_not_position_or_pv_time(self):
        a, b = measurement(0., horizon=1.), measurement(2., horizon=2.)
        for variant in b['variants']:
            variant['queries'].reverse()
        result = assembly.pair_contrasts(a, b, FEATURES)
        pv = query(result, 'common_pv', .0025)
        physical_time = query(result, 'common_physical_time', .25)
        self.assertTrue(pv['available'])
        self.assertTrue(physical_time['available'])
        self.assertEqual(pv['features'][DISPLACEMENT]['fine_difference'], 2.)
        self.assertEqual(physical_time['features'][DISPLACEMENT]['fine_difference'], 2.)

    def test_inapplicable_sphere_angle_never_becomes_zero_effect(self):
        result = assembly.pair_contrasts(measurement(0.), measurement(2.), FEATURES)
        for fields in [result['summary']['features'], *(q['features'] for q in result['queries'])]:
            self.assertFalse(fields[ANGLE]['available'])
            self.assertFalse(fields[ANGLE]['resolved'])
            self.assertEqual(fields[ANGLE]['reason'], 'inapplicable_or_missing_feature')
            self.assertNotIn('fine_difference', fields[ANGLE])
            self.assertTrue(fields[DISPLACEMENT]['resolved'])

    def test_early_export_blocks_endpoint_summary_but_preserves_observed_queries(self):
        a, b = measurement(0.), measurement(2.)
        for variant in a['variants']:
            variant['summary'].update(observed_stop_s=.3, whole_body_control_volume_export=True)
            late = next(q for q in variant['queries'] if q['kind'] == 'common_pv' and q['target_pv'] == .005)
            late.clear()
            late.update(kind='common_pv', target_pv=.005, time_s=.5,
                        available=False, reason='export_before_query')
        result = assembly.pair_contrasts(a, b, FEATURES)
        self.assertTrue(result['available'])
        self.assertFalse(result['summary']['available'])
        self.assertNotIn('features', result['summary'])
        self.assertTrue(query(result, 'common_pv', .0025)['available'])
        self.assertTrue(query(result, 'common_physical_time', .25)['available'])
        self.assertFalse(query(result, 'common_pv', .005)['available'])
        self.assertNotIn('features', query(result, 'common_pv', .005))
        self.assertEqual(result['endpoint_primary_export_difference'], -1)

    def test_any_unavailable_variant_blocks_only_that_query(self):
        for index in range(4):
            for flag in (False, None, 1, 'True'):
                a, b = measurement(0.), measurement(2.)
                variants = [*a['variants'], *b['variants']]
                variants[index]['queries'][0]['available'] = flag
                result = assembly.pair_contrasts(a, b, FEATURES)
                with self.subTest(index=index, flag=flag):
                    self.assertFalse(query(result, 'common_pv', .0025)['available'])
                    self.assertTrue(query(result, 'common_physical_time', .25)['available'])

    def test_missing_and_nearby_targets_are_not_interpolated_or_imputed(self):
        a, b = measurement(0.), measurement(2.)
        b['variants'][1]['queries'].pop(2)
        result = assembly.pair_contrasts(a, b, FEATURES)
        self.assertFalse(query(result, 'common_pv', .005)['available'])
        a, b = measurement(0.), measurement(2.)
        near = math.nextafter(.0025, math.inf)
        b['variants'][1]['queries'][0]['target_pv'] = near
        result = assembly.pair_contrasts(a, b, FEATURES)
        self.assertFalse(query(result, 'common_pv', .0025)['available'])
        self.assertFalse(query(result, 'common_pv', near)['available'])
        self.assertTrue(query(result, 'common_physical_time', .25)['available'])

    def test_duplicate_query_target_is_rejected(self):
        a, b = measurement(0.), measurement(2.)
        duplicate = copy.deepcopy(a['variants'][0]['queries'][0])
        duplicate['time_s'] = .24
        a['variants'][0]['queries'].append(duplicate)
        with self.assertRaises((ValueError, TypeError)):
            assembly.pair_contrasts(a, b, FEATURES)

    def test_missing_case_and_bad_available_features_do_not_form_contrasts(self):
        result = assembly.pair_contrasts(None, measurement(2.), FEATURES)
        self.assertFalse(result['available'])
        self.assertIsNone(result['summary'])
        self.assertEqual(result['queries'], [])
        for value in (math.nan, math.inf, True, '0'):
            a, b = measurement(0.), measurement(2.)
            a['variants'][0]['summary'][DISPLACEMENT] = value
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    assembly.pair_contrasts(a, b, FEATURES)


if __name__ == '__main__':
    unittest.main(verbosity=2)
