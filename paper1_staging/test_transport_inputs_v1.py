"""Input/immutability controls only: zero particle transport or GPU updates."""
from pathlib import Path
from types import SimpleNamespace, FunctionType
from unittest.mock import patch
import copy, hashlib, sys, unittest
import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'stage115_staging')]
import immutable_field_scope_v1 as snapshot
import transport_cases_v1 as cases
import corrected_transport_v1 as transport


def require(ok, message):
    if not ok: raise RuntimeError(message)


class Controls(unittest.TestCase):
    def metadata(self, flow):
        return dict(cpd=6, flow_factor=flow, normalization_to_target_applied=False,
                    achieved_mean_interstitial_velocity_m_s=flow * 1e-4,
                    cell_length_m=.005, pv_per_second=flow * .02)

    def test_complete_matrix_and_refinement_convention(self):
        contract = cases.contract()
        physical = cases.fields.read(contract['physical_design_file'])
        preserved = ('dynamic_viscosity_Pa_s', 'fluid_density_kg_m3', 'particle_density_kg_m3',
                     'friction_coefficient', 'gravity_m_s2', 'added_mass_fraction', 'prolate_semiaxes_m', 'trap')
        matched = {}
        for core in contract['cases']:
            old = next(x for x in physical['cases'] if x['shape'] == core['shape']
                       and x['sample_id'] == core['placement_id'])
            for factor in (.125, .0625, .03125):
                out = cases.case_for(core['id'], self.metadata(core['nominal_flow_level']), .025, factor)
                spec = out['spec']; cfg = spec['config']; before = old['spec']['config']
                self.assertEqual(spec['refinement'], .0078125 * factor / .125)
                self.assertEqual(spec['sample_id'], core['placement_id'])
                self.assertEqual(spec['horizon_s'] * self.metadata(core['nominal_flow_level'])['pv_per_second'], .025)
                self.assertEqual({k: cfg[k] for k in preserved}, {k: before[k] for k in preserved})
                for key in cases.SCALED_CONTROLS:
                    self.assertEqual(cfg['numerics'][key], before['numerics'][key] * factor / .125)
                for key in set(before['numerics']) - set(cases.SCALED_CONTROLS):
                    self.assertEqual(cfg['numerics'][key], before['numerics'][key])
                pair = (core['placement_id'], core['nominal_flow_level'], factor)
                if pair in matched: self.assertEqual(spec['initial_state'], matched[pair])
                matched[pair] = spec['initial_state']
        self.assertEqual(len(matched), 18)

    def test_unfrozen_core_and_changed_flow_rejected(self):
        ident = cases.contract()['cases'][0]['id']
        with self.assertRaises((RuntimeError, FileNotFoundError)):
            cases.case_for(ident, self.metadata(.5), .025, mode='core')
        with self.assertRaises(RuntimeError): cases.case_for(ident, self.metadata(2.), .025)
        with self.assertRaises(RuntimeError): cases.case_for(ident, self.metadata(.5), .02)

    def api(self, mutate=False):
        field_module = SimpleNamespace(load=lambda *a: None)
        runner = type('Runner', (), {})
        def dispatch(cls, spec, field, geometry, wall_budget):
            if mutate: field.u = field.u.copy()
            return field.u.copy()
        space = dict(transport.execute.__globals__, fields=field_module, BoundRunner=runner,
                     dispatch=dispatch, frozen=SimpleNamespace(h=SimpleNamespace(geometry_exact_v1=SimpleNamespace(
                         GrainGeometry=lambda *args: args))))
        fn = FunctionType(transport.execute.__code__, space, 'execute', transport.execute.__defaults__)
        return SimpleNamespace(fields=field_module, execute=fn, require=require,
                               verify_mapping=transport.verify_mapping)

    def test_original_execute_equivalence_and_storage_controls(self):
        field = SimpleNamespace(u=np.arange(24., dtype=np.float64).reshape(3, 2, 2, 2),
                                fluid=np.ones((2, 2, 2), dtype=bool))
        data = dict(sand_centres_m=np.zeros((1, 3)), sand_radii_m=np.ones(1))
        for flow in (.5, 1., 2.):
            api = self.api(); old_execute, old_load = api.execute, api.fields.load
            meta = self.metadata(flow)
            spec = dict(seed=2, flow_factor=flow, cpd=6, field_metadata=meta)
            with patch.object(snapshot.reader, 'load', return_value=(field, data, meta)) as loader:
                with snapshot.scope(api, (2, flow, 6), meta) as scoped:
                    out = api.execute(spec, 'diagnostic', 45, pause=1)
                    self.assertTrue(np.array_equal(out, field.u))
                    fixed, _, small = api.fields.load(2, flow, 6)
                    with self.assertRaises(ValueError): fixed.u.flat[0] = -1
                    with self.assertRaises(ValueError): fixed.u.setflags(write=True)
                    with self.assertRaises(RuntimeError): api.fields.load(2, flow, 4)
                    with self.assertRaises(RuntimeError): scoped['digest'](copy.deepcopy(field))
                    small['cell_length_m'] = -1
                    self.assertEqual(api.fields.load(2, flow, 6)[2], meta)
                    self.assertEqual(loader.call_count, 1)
            self.assertIs(api.execute, old_execute); self.assertIs(api.fields.load, old_load)

    def test_mutation_and_exception_restore_original_functions(self):
        api = self.api(mutate=True); old_execute, old_load = api.execute, api.fields.load
        meta = self.metadata(1.)
        field = SimpleNamespace(u=np.zeros((3, 1, 1, 1)))
        data = dict(sand_centres_m=np.zeros((1, 3)), sand_radii_m=np.ones(1))
        with patch.object(snapshot.reader, 'load', return_value=(field, data, meta)):
            with self.assertRaises(RuntimeError):
                with snapshot.scope(api, (2, 1., 6), meta):
                    api.execute(dict(seed=2, flow_factor=1., cpd=6, field_metadata=meta), 'diagnostic', 45)
        self.assertIs(api.execute, old_execute); self.assertIs(api.fields.load, old_load)


if __name__ == '__main__': unittest.main()
