"""Pure preparation controls; no simulation or authority is constructed."""
import copy
import importlib.util
from pathlib import Path

SELF = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location('_prep_momentum_controls', SELF.with_name('prepare_saved_momentum_probe_v1.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
budget = p.budget_envelope()
assert budget['maximum_new_all_trial_work_rows'] == 256 + 4 == 260
assert budget['maximum_new_integration_records'] == 1 + 4 == 5
assert budget['original_spent']['nonadvancing_charge'] + budget['maximum_nonadvancing_invocation_units'] == 22
assert budget['original_spent']['work_rows'] + 260 == budget['worst_case_original_after']['work_rows']
assert budget['original_spent']['records'] + 5 == budget['worst_case_original_after']['records']
assert budget['original_spent']['admitted_physical_rows'] + budget['original_spent']['admitted_discarded_rows'] + budget['original_spent']['known_unaccepted_rows'] + budget['original_spent']['old_unknown_reserved_rows'] == 757577
assert p.merge({'a': 'x'}, {'a': 'x', 'b': 'y'}) == {'a': 'x', 'b': 'y'}
try:
    p.merge({'a': 'x'}, {'a': 'z'})
except ValueError:
    pass
else:
    raise AssertionError('conflicting frozen input accepted')
assert all(not x.exists() for x in p.forbidden())

def reject(fn):
    try:
        fn()
    except (ValueError, KeyError):
        return
    raise AssertionError('invalid evidence accepted')

actors = [dict(launch=dict(pid=i+1, created=float(i), command=['python', str(i)]),
               inspection=dict(retired=True)) for i in range(8)]
new = dict(identities=actors[:4]); old = dict(exact_retirement_after=actors[4:])
assert len(p.prior_identity_inventory(new, old)) == 8
reject(lambda: p.prior_identity_inventory(new, {}))
reject(lambda: p.prior_identity_inventory(new, dict(exact_retirement_after=[])))
bad = copy.deepcopy(old); bad['exact_retirement_after'][0]['launch'].pop('created')
reject(lambda: p.prior_identity_inventory(new, bad))
bad = copy.deepcopy(old); bad['exact_retirement_after'][0]['launch'] = copy.deepcopy(actors[0]['launch'])
reject(lambda: p.prior_identity_inventory(new, bad))

origin = dict(x=[1], p=[2], q=[3], t=4, history_node='h', history_length=1972)
maps = [dict(inner_index=i, input_sha256=str(i), map_output=[i], health={}) for i in range(2)]
def branch(name, h):
    return dict(branch_id='m000000547_t000000000_'+name, before_state=copy.deepcopy(origin),
        normal_gap_operand_policy=dict(prepare_calls=[dict(metadata=[dict(context={})])]),
        cap_entries=[dict(actual_trial_dt_s=h)], contact_trial_trace=dict(
            cycle_guard_trials=[dict(records=copy.deepcopy(maps))], detailed_trials=[dict(
                accepted=False, error="RuntimeError('inertial momentum closure failed')", outer_inputs=[0]*14)]))
branches = [None]*1643; branches[1641] = branch('C', 2.); branches[1642] = branch('F1', 1.)
wire = dict(packet=dict(work_branches=branches))
arithmetic = dict(per_inner=[dict(branch_index=n, exact_inner_input_sha256=str(i),
    exact_free_closure_guard_would_activate=n==1642) for n in (1641,1642) for i in range(2)],
    original_failure=dict(normalized_residual=2e-8))
fixtures = p.build_fixtures(wire, arithmetic)
assert fixtures['F1']['directly_stored_outer_inputs'] and not fixtures['C']['directly_stored_outer_inputs']
bad = copy.deepcopy(wire); bad['packet']['work_branches'][1641]['before_state']['q'] = [99]
reject(lambda: p.build_fixtures(bad, arithmetic))
bad = copy.deepcopy(arithmetic); bad['per_inner'][0]['exact_inner_input_sha256'] = 'tampered'
reject(lambda: p.build_fixtures(wire, bad))
bad = copy.deepcopy(wire); bad['packet']['work_branches'][1642]['branch_id'] = 'later_easier'
reject(lambda: p.build_fixtures(bad, arithmetic))
print('{"passed":true,"pure_controls":18,"native_force_calls":0,"transport_steps":0,"authority_created":false}')
