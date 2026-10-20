"""Stdlib/source/retained-metadata controls only; no model/runner imports."""
import ast
import copy
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import prepare_contact_event_diagnostic_v1 as p


def inputs():
    source=p.sealed(p.SOURCE2,p.SOURCE2_SHA)
    preview=p.read(p.SEEDS/'physical_cases_preview.json')
    seeds={level:json.loads(lzma.decompress((p.SEEDS/(level+'.json.xz')).read_bytes())) for level in p.PREPARED_LEVELS}
    original=p.read(p.ORIGINAL_PHYSICAL); proposal=p.read(p.ORIGINAL_PROPOSAL)
    return source,preview,seeds,original,proposal


def documents(values=None):
    source,preview,seeds,original,proposal=values or inputs()
    return p.build_documents(source,preview,seeds,original,proposal,
        {'source':'0'*64},{'physical':'1'*64},{'receipt':'2'*64},'3'*64,{'old':'4'*64})


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values=inputs()
        cls.seed_pins={str(path):p.sha(path) for path in p.SEEDS.glob('*') if path.is_file()}

    @classmethod
    def tearDownClass(cls):
        for path,expected in cls.seed_pins.items():
            if p.sha(path)!=expected: raise AssertionError('Preserved seed bytes changed')

    def test_authenticated_three_FULL_seeds_and_literal_1972_history(self):
        source,preview,seeds,original,proposal=copy.deepcopy(self.values)
        cases={case['level_id']:case for case in preview['cases']}
        summaries={row['level_id']:row for row in source['prospective_seed_checks']}
        states=[p.validate_seed(seeds[level],cases[level],summaries[level],p.digest(preview)) for level in p.PREPARED_LEVELS]
        self.assertTrue(all(state==states[0] for state in states))
        self.assertEqual(states[0]['t'],p.START_S)
        self.assertEqual(states[0]['steps'],493074)
        self.assertEqual(len(states[0]['history']),1972)
        self.assertIsNone(states[0]['pending_trial'])

    def test_native_config_copies_original_gap_semantics_without_rebinding(self):
        before=copy.deepcopy(self.values)
        config,proposal=documents(self.values)
        self.assertEqual(self.values,before)
        self.assertEqual(config['cases'],self.values[1]['cases'])
        self.assertEqual(config['minimum_gap_semantics'],self.values[3]['minimum_gap_semantics'])
        self.assertNotIn('minimum_gap_semantics',self.values[1])
        self.assertEqual(config['inherited_preview_binding'],self.values[1]['binding'])
        self.assertFalse(config['silently_rebound_seed'])
        self.assertFalse(proposal['numerical_launch_ready'])
        self.assertFalse(proposal['authorization_created'])
        self.assertFalse(proposal['clock_created'])
        self.assertEqual(proposal['qualified_core_cases'],1)
        self.assertEqual([item['level_id'] for item in proposal['levels']],['f0p0625','f0p03125'])
        self.assertEqual(config['source_prepared_undispatched_levels'],['f0p125'])
        self.assertTrue(proposal['future_full_three_factor_qualification_still_required'])
        self.assertTrue(proposal['diagnostic_contract']['positive_grain15_loading_required'])
        self.assertTrue(proposal['diagnostic_contract']['loading_from_committed_independently_audited_native_branches_only'])
        self.assertTrue(proposal['coverage_contract']['requires_original_accepted_contact_health_lambda_n_grain15_strictly_positive'])
        self.assertTrue(proposal['coverage_contract']['missing_actual_loading_is_incomplete_not_success'])

    def test_reject_modified_seed_contract_state_history_controller_or_limits(self):
        source,preview,seeds,original,proposal=self.values
        case=next(row for row in preview['cases'] if row['level_id']=='f0p0625')
        summary=next(row for row in source['prospective_seed_checks'] if row['level_id']=='f0p0625')
        changes=(
            lambda s:s['case'].__setitem__('binding','0'*64),
            lambda s:s['checkpoint']['physical_checkpoint']['state']['x'].__setitem__(0,99.),
            lambda s:s['checkpoint']['physical_checkpoint']['state']['history'].pop(),
            lambda s:s['checkpoint']['physical_checkpoint'].__setitem__('contract','0'*64),
            lambda s:s['checkpoint']['cursor'].__setitem__('phase','after_first_half'),
            lambda s:s['checkpoint']['numeric_ledger'].__setitem__('all_work_rows',1),
            lambda s:s['checkpoint'].__setitem__('spec_sha256','0'*64),
            lambda s:s['checkpoint']['frames'][s['checkpoint']['published_state_token']].__setitem__('parent','0'*64),
            lambda s:s['limits'].__setitem__('velocity_defect_over_U',1.),
        )
        for change in changes:
            altered=copy.deepcopy(seeds['f0p0625']);change(altered)
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                p.validate_seed(altered,case,summary,p.digest(preview))

    def test_no_missing_factors_or_changed_physics_scales_horizon(self):
        for label in ('missing','factor','physics','limit','end'):
            values=copy.deepcopy(self.values)
            source,preview,seeds,original,proposal=values
            if label=='missing': seeds.pop('f0p125')
            elif label=='factor': preview['cases'][0]['factor']=.5
            elif label=='physics': original['cases'][0]['spec']['config']['friction_coefficient']=0.
            elif label=='limit': proposal['levels'][0]['limits']['minimum_h_s']=1e-8
            else: preview['common_end_time_s']+=.0001
            with self.subTest(label=label),self.assertRaises((ValueError,KeyError)):
                documents(values)

    def test_budget_constructive_envelopes_and_precise_baseline(self):
        b=p.budget()
        self.assertEqual(b['constructive_success_envelope_work_rows'],132648)
        self.assertEqual(b['constructive_success_envelope_records'],69)
        self.assertEqual(b['within_same_caps_unallocated_work_rows'],7352)
        self.assertEqual(b['within_same_caps_unallocated_records'],3)
        self.assertEqual(b['remaining_after_maximum']['standalone_all_work_rows'],48631)
        self.assertEqual(b['remaining_after_maximum']['standalone_records'],41)
        self.assertEqual(b['baseline']['diagnostic_work_rows'],146081+11369)
        self.assertEqual(b['baseline']['diagnostic_records'],66+37)
        old=b['prior_four_attempts']
        self.assertEqual(sum(old[key] for key in ('admitted_physical_half_rows','admitted_discarded_rows','known_unaccepted_rows','unknown_reserved_rows')),752798)
        self.assertEqual(old['unknown_reserved_rows'],4838)
        with patch.object(p,'INITIAL_CAP',1024):
            with self.assertRaises(ValueError):p.budget()
        values=copy.deepcopy(self.values);values[0]['old_unknown_reserved_work_rows']=0
        with self.assertRaises(ValueError):documents(values)

    def test_split_COMBINED_cap_rejects_two_independent_full_right_reservations(self):
        self.assertEqual(p.validate_split_charge(4998,1000,3998),3998)
        self.assertEqual(p.validate_split_charge(768,1,767),767)
        for args in ((4998,1,4998),(768,100,768),(4998,4999,0),(4998,False,0),(0,0,0)):
            with self.subTest(args=args),self.assertRaises(ValueError):p.validate_split_charge(*args)

    def test_original_absolute_clock_cannot_be_reset(self):
        clock=p.read(p.OUTER_CLOCK);p.validate_clock(clock)
        for key in ('start_utc','simulation_cutoff_utc','end_utc'):
            altered=copy.deepcopy(clock);altered[key]='2026-10-25T00:00:00+00:00'
            with self.subTest(key=key),self.assertRaises(ValueError):p.validate_clock(altered)
        scope=p.approval_scope()
        self.assertEqual(scope['maximum_window_minutes'],120)
        self.assertEqual(scope['maximum_native_minutes'],60)
        self.assertEqual(scope['original_shared_end_utc'],clock['end_utc'])

    def test_access_denial_or_missing_birth_command_is_not_retirement(self):
        closed=p.sealed(p.CLOSED,p.CLOSED_SHA);p.validate_retirement(closed)
        for label in ('birth','command','denied','one_actor_missing'):
            altered=copy.deepcopy(closed)
            if label=='birth':altered['exact_retirement_after'][0]['launch']['created']=None
            elif label=='command':altered['exact_retirement_after'][0]['launch']['command']=[]
            elif label=='denied':altered['exact_retirement_after'][0]['inspection']=dict(retired=True,access_denied=True)
            else:altered['exact_retirement_after'].pop()
            with self.subTest(label=label),self.assertRaises((ValueError,TypeError)):p.validate_retirement(altered)

    def test_fresh_process_identity_reads_birth_before_command_and_never_acts(self):
        class Gone(Exception):pass
        class Denied(Exception):pass
        launch=dict(pid=77,created=100.,command=['python.exe','-B','original.py'])
        def inspect(birth,command,constructor=None):
            calls=[]
            def create_time():
                calls.append('birth')
                if isinstance(birth,Exception):raise birth
                return birth
            def cmdline():
                calls.append('command')
                if isinstance(command,Exception):raise command
                return command
            def process(pid):
                calls.append(('Process',pid))
                if constructor is not None:raise constructor
                return SimpleNamespace(create_time=create_time,cmdline=cmdline)
            api=SimpleNamespace(Process=process,NoSuchProcess=Gone)
            return p.fresh_identity_retirement(launch,api),calls
        gone,calls=inspect(100.,launch['command'],Gone())
        self.assertTrue(gone['retired']);self.assertTrue(gone['no_such_process'])
        mismatch,calls=inspect(101.,Denied())
        self.assertTrue(mismatch['retired']);self.assertTrue(mismatch['proven_birth_mismatch'])
        self.assertNotIn('command',calls,'different proven birth excludes unrelated inaccessible process')
        mismatch,calls=inspect(100.,['unrelated.exe'])
        self.assertTrue(mismatch['retired']);self.assertTrue(mismatch['proven_full_command_mismatch'])
        self.assertEqual(calls,[('Process',77),'birth','command'])
        live,calls=inspect(100.,launch['command'])
        self.assertFalse(live['retired']);self.assertTrue(live['exact_original_identity_live'])
        for birth,command in ((100.,Denied()),(Denied(),launch['command']),
                              (Denied(),['unrelated.exe']),(float('nan'),launch['command']),(0.,launch['command'])):
            result,calls=inspect(birth,command)
            self.assertFalse(result['retired']);self.assertTrue(result['identity_unresolved'])
            self.assertIn('command',calls,'unreadable/nonmismatched birth still requires exact command inspection')

    def test_fresh_all_four_identity_gate_refuses_unresolved_access(self):
        closed=p.sealed(p.CLOSED,p.CLOSED_SHA)
        class Gone(Exception):pass
        class Denied(Exception):pass
        def absent(pid):raise Gone()
        api=SimpleNamespace(Process=absent,NoSuchProcess=Gone)
        observations=p.fresh_old_retirements(closed,api)
        self.assertEqual(len(observations),4)
        self.assertTrue(all(row['inspection']['retired'] for row in observations))
        def denied(pid):raise Denied()
        api.Process=denied
        with self.assertRaisesRegex(ValueError,'fresh original identity retirement unresolved'):
            p.fresh_old_retirements(closed,api)

    def test_create_only_documents_and_no_authority_side_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'nested/proposal.json'
            p.create_json(path,{'dispatch_authorized':False})
            before=path.read_bytes()
            with self.assertRaises(FileExistsError):p.create_json(path,{'bad':True})
            self.assertEqual(path.read_bytes(),before)
            allowed=Path(folder)/'must_not_exist'
            p.no_future_authority((allowed,))
            allowed.mkdir()
            with self.assertRaises(ValueError):p.no_future_authority((allowed,))

    def test_fake_missing_pin_rejected_before_any_prospective_write(self):
        with tempfile.TemporaryDirectory() as folder:
            pins=Path(folder)/'pins.json';pins.write_text('{}')
            with self.assertRaises(ValueError):p.prepare(pins,'0'*64)
        self.assertFalse(p.FAMILY.joinpath('authorization_01.json').exists())
        self.assertFalse(p.FAMILY.joinpath('window_clock_01').exists())
        self.assertFalse(p.OUT.exists())

    def test_source_only_metadata_parser_has_no_execution_escape(self):
        source="MAX_WORK, MAX_RECORDS=140000,72\nBASELINE=dict(case_records=2360)\ndef approval_scope():\n return dict(work=MAX_WORK, calls=MAX_RECORDS)\n"
        self.assertEqual(p.runner_metadata(source),dict(approval_scope=dict(work=140000,calls=72),baseline=dict(case_records=2360),diagnostic_contract=None))
        for source in ("def approval_scope():\n return open('authority','w')\n",
                       "def approval_scope():\n print('side effect')\n return dict()\n"):
            with self.assertRaises(ValueError):p.runner_metadata(source)

    def test_no_model_runner_or_execution_import_in_preparer(self):
        tree=ast.parse(Path(p.__file__).read_text())
        imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom):imports.append(node.module)
        self.assertTrue(set(imports)<={'pathlib','datetime','argparse','ast','copy','hashlib','json','lzma','math','os','subprocess','sys','psutil'})
        self.assertNotIn('run_contact_event_diagnostic_v1',imports)

    def test_positive_main_requires_fresh_FULL_hash_map_before_any_artifact(self):
        tree=ast.parse(Path(p.__file__).read_text())
        main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='prepare')
        calls=[node for node in ast.walk(main) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)]
        full=[node for node in calls if node.func.id=='verify_mapping' and len(node.args)==1
              and isinstance(node.args[0],ast.Name) and node.args[0].id=='historical']
        writes=[node for node in calls if node.func.id=='create_json']
        self.assertEqual(len(full),1)
        self.assertLess(full[0].lineno,min(node.lineno for node in writes))
        retire=[node for node in calls if node.func.id=='fresh_old_retirements']
        self.assertEqual(len(retire),2)
        self.assertLess(min(node.lineno for node in retire),full[0].lineno)
        self.assertGreater(max(node.lineno for node in retire),full[0].lineno)
        self.assertLess(max(node.lineno for node in retire),min(node.lineno for node in writes))


if __name__=='__main__':
    unittest.main(verbosity=2)
