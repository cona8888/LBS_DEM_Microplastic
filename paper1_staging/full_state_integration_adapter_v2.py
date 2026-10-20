"""Scope-order repair of preserved V1; no launcher or execution authority.

The original generated rigid-rotation integrator is compiled into a machine:
its initialization runs once at a packet boundary and its unchanged physical
loop body is an internal branch callable.  Coarse/fine work is not dispatched
through the Python campaign API once per physical step.  Growing literal
history is structurally shared; original FULL hashes are formed only at packet
boundaries.  Compact state tokens are explicitly NOT original FULL hashes.

Native qualification, the independent mechanical-stencil/composition audit,
source-bound capture qualification and timing approval remain separate gates.
Importing or compiling this module never warms or calls a contact solver.
"""
from contextlib import contextmanager, ExitStack, nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import FunctionType, SimpleNamespace
import ast
import copy
import hashlib
import importlib
import inspect
import json
import math
import time

import full_state_stepdoubling_v1 as policy

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SCHEMA = 'paper1.full-state-stepdoubling.packet.v1'
CHECKPOINT_SCHEMA = 'paper1.full-state-stepdoubling.checkpoint.v1'
SOURCE_PINS = {
    'stage119_staging/checkpoint_core_v3.py': '42db6447af1f9c9ef7782ec726702acd11f2f43dcd4eb2fc8aaf3d6dc4c6d5a6',
    'stage151_staging/rigid_rotation_v1.py': '71477947abba618aa5f86124e00389aec99d1a6908a507a5510b452324b3c288',
    'stage153_staging/modal_rotation_dt_v1.py': '3992a79c06e04e9690154d5ca85a339b774da46080aa0b9ca2ac41e7d79da3bd',
    'stage42_staging/inertial_contact_robust_v1.py': '22909a9b5bdd7f86fbf13e9b7c3cb804024fe2fb919d19438ef11c0bf0e0a43b',
    'stage37_staging/transport_contact.py': '6bf53d779b7517b86c825c0a9eecbfccded7f497898d09f070dde3a046424e9a',
    'stage213_staging/normal_gap_scope_v1.py': '685e501dc0cf93a871ff4eb2f292ef183b657f2679b8365f971f713229f23070',
    'stage243_staging/per_pose_guard_v1.py': '8a083685b2f1f28ff37fa08f75919603c0d0c22d540d32d0196cc7d2af0d5d6f',
    'paper1_staging/contact_onset_timecap_v1.py': 'efac7c7964c10156aaef5c59f45edfc2fde0c3f11a11859bd8e56933ab370b8a',
    'stage104_staging/trajectory_failure_only_rescue_v1.py':'8b637d699b327fd58a836d8eae028a016e1601b248d7d0c0808838adc73c9608',
    'stage89_staging/trajectory_short_pgs_seed_v1.py':'acff5e180c302c3f5061f64aad5e6103c570e18e1db03db0f2b100a9d7d76541',
    'stage81_staging/trajectory_combined_scalar_v1.py':'be43ad045f4cb99be808e68f782533a17e9a2ee12ba64438d9bbf2a8af6604c7',
    'stage80_staging/trajectory_combined_pruning_v1.py':'c8d8a4582bf21d8c36a3f5d0b2aec99a98309561f7f4f16fade326491b0b01d5',
    'stage117_staging/longer_sentinels_v1.py':'08a6bd5d451463c30d5183711e1f7132b7022f091d73fbb633bd3445949b83b3',
    'paper1_staging/full_state_integration_adapter_v1.py':'01001f8f74c42064da2dcb719aec6ba5670fbb3e060f59fac0c4b03579d8fd72',
}


class Stop(policy.Stop):
    pass


def need(value, message):
    if not value:
        raise Stop('Original-substep adapter: ' + message)


def plain(value):
    if hasattr(value, 'tolist'):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'item'):
        return value.item()
    return copy.deepcopy(value)


def token(value):
    value=plain(value)
    def valid(x):
        if isinstance(x,float):need(not math.isnan(x),'NaN is not an original history sentinel')
        elif isinstance(x,dict):
            for item in x.values():valid(item)
        elif isinstance(x,(list,tuple)):
            for item in x:valid(item)
    valid(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), allow_nan=True).encode()).hexdigest()


def original_digest(value):
    """Original Stage115 default JSON spacing, only at FULL boundaries."""
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True,
                                     allow_nan=True).encode()).hexdigest()


def validate_outer_checkpoint_admission(checkpoint, expected_policy_binding, expected_source_sha):
    """Pure admission guard. An old bare physical checkpoint is never credit.

    This runs before construction of the original machine. The caller also
    authenticates its sealed enclosing packet/receipt; this function does not
    turn a syntactically plausible document into trusted evidence.
    """
    if checkpoint is None:
        return True
    need(isinstance(checkpoint,dict) and checkpoint.get('schema')==CHECKPOINT_SCHEMA,
         'new-controller outer checkpoint required; old physical FULL is read-only evidence')
    need(checkpoint.get('adapter_source_sha256')==expected_source_sha,
         'outer checkpoint exact adapter source binding')
    need(checkpoint.get('policy_sha256')==expected_policy_binding,
         'outer checkpoint exact numerical policy binding')
    need(isinstance(checkpoint.get('physical_checkpoint'),dict)
         and isinstance(checkpoint.get('cursor'),dict), 'complete outer physical/cursor state')
    return True


def history_node(parent, delta):
    return parent if not delta else token(dict(parent_history_node=parent, history_delta=delta))


def state_token(parent, header, delta):
    return token(dict(kind='logical-state-history-token-not-full-checkpoint',
                      parent_token=parent, state_header=header, appended_history_rows=delta))


def choose_clock_interval(time_s, original_cap_s, minimum_h_s, maximum_halvings):
    """Literal representable midpoint; no force, extension or interpolation.

    The two original fine steps use midpoint-origin and endpoint-midpoint.
    They can differ only by endpoint roundoff, disclosed explicitly. This
    preserves the original horizon clip without an artificial tiny remainder.
    """
    need(all(math.isfinite(x) for x in (time_s,original_cap_s,minimum_h_s))
         and time_s>=0 and original_cap_s>0 and minimum_h_s>0,'finite original clock cap')
    need(type(maximum_halvings)is int and 0<=maximum_halvings<=8,'frozen bounded retry ceiling')
    h=original_cap_s;mid=time_s+h/2;end=time_s+h
    first,second=mid-time_s,end-mid
    band=2*math.ulp(max(abs(time_s),abs(end)))
    need(h>=minimum_h_s and time_s<mid<end and abs(first-second)<=band,
         'positive bounded literal midpoint intervals before any force')
    return dict(h_s=h,end_time_s=end,midpoint_time_s=mid,first_interval_s=first,second_interval_s=second,
        half_duration_difference_s=abs(first-second),maximum_half_duration_difference_s=band,
        maximum_halvings=maximum_halvings,
        policy='literal-representable-midpoint-roundoff-split-v1',original_selected_cap_s=original_cap_s)


class History:
    """A mutable cursor over immutable append nodes, never a per-step list copy."""
    def __init__(self, store, node):
        self.store, self.node = store, node

    def append(self, row):
        delta = [plain(row)]
        new = history_node(self.node, delta)
        self.store.add(new, self.node, delta)
        self.node = new

    def fork(self):
        return History(self.store, self.node)

    def __deepcopy__(self, memo):
        return self.fork()


class HistoryStore:
    def __init__(self, literal, descriptor=None):
        self.literal = plain(literal)
        self.descriptor = descriptor
        self.nodes = {}
        self.root = None

    def start(self, full_sha):
        if self.descriptor is None:
            self.descriptor = dict(boundary_full_checkpoint_sha256=full_sha,
                history_sha256=token(self.literal), history_length=len(self.literal))
        n = self.descriptor['history_length']
        need(0 <= n <= len(self.literal) and token(self.literal[:n]) == self.descriptor['history_sha256'],
             'immutable literal history root')
        self.root = token(self.descriptor)
        self.nodes[self.root] = dict(parent=None, delta=self.literal[:n], length=n)
        current = self.root
        for row in self.literal[n:]:
            new = history_node(current, [row])
            self.add(new, current, [row]); current = new
        return History(self, current)

    def add(self, node, parent, delta):
        need(parent in self.nodes and node == history_node(parent, delta), 'history append identity')
        value = dict(parent=parent, delta=plain(delta), length=self.nodes[parent]['length'] + len(delta))
        need(node not in self.nodes or self.nodes[node] == value, 'unambiguous immutable history node')
        self.nodes[node] = value

    def suffix(self, node, parent):
        values = []
        while node != parent:
            need(node in self.nodes and self.nodes[node]['parent'] is not None, 'history ancestor')
            value = self.nodes[node]; values.append(value['delta']); node = value['parent']
        return [x for block in reversed(values) for x in block]

    def materialize(self, node):
        return self.nodes[self.root]['delta'] + self.suffix(node, self.root)


def decision_values(limits, origin, coarse, first, second, h, cap, depth):
    """Same arithmetic as the pure kernel, using honestly named logical tokens."""
    limits.validate()
    need(0 <= depth <= limits.maximum_halvings and limits.minimum_h_s <= h <= cap,
         'bounded tightening only')
    t = origin['state']['t']
    need(coarse['state']['t'] == second['state']['t'] == t+h
         and first['state']['t'] == t+h/2, 'exact common clock, no alignment or interpolation')
    need(coarse['parent'] == first['parent'] == origin['token']
         and second['parent'] == first['token'], 'FULL logical ancestry')
    c, f = coarse['state'], second['state']
    dx, dp = policy.difference(c['x'], f['x']), policy.difference(c['p'], f['p'])
    dq = policy.difference(c['q'], f['q']) / limits.speed_m_s
    score = max(dx/limits.position_defect_m, dp/limits.director_defect,
                dq/limits.velocity_defect_over_U)
    need(math.isfinite(score), 'finite defect')
    passing = score <= 1
    if not passing:
        need(depth < limits.maximum_halvings and h/2 >= limits.minimum_h_s,
             'bounded accuracy rejection, never force acceptance')
    return dict(action='commit_literal_halves' if passing else 'discard_all_and_halve',
        position_defect_m=dx, director_defect=dp, velocity_defect_over_U=dq,
        scaled_defect=score, next_h_s=h if passing else h/2,
        next_halving_depth=depth if passing else depth+1,
        committed_state_token=second['token'] if passing else None,
        witness_semantics='controller_state_token_not_original_FULL_sha')


def compile_machine(source, namespace):
    """Compile the actual generated integrator, changing administration only.

    The original while-body statements (including retries, health, sweep, pose,
    dwell and history append) remain in an internal one-branch function.  The
    only mechanical-loop additions are a min-dt cap and a counted call wrapper.
    Original snapshot/checkpoint administration is replaced by structural state
    capture; no original physical equation or terminal movement is replaced.
    """
    tree = ast.parse(source); original = copy.deepcopy(tree)
    fn = tree.body[0]
    need(isinstance(fn, ast.FunctionDef) and fn.name == 'integrate', 'actual generated integrate')
    outer = next(n for n in fn.body if isinstance(n, ast.Try))
    loop = outer.body[0]
    need(isinstance(loop, ast.While) and len(outer.body) == 2, 'original single physical loop and horizon return')
    snapshot = next(n for n in fn.body if isinstance(n, ast.FunctionDef) and n.name == 'snapshot')
    old_return = snapshot.body[-1]
    need(isinstance(old_return, ast.Return) and "'state_sha256'" in ast.unparse(old_return), 'original snapshot layout')
    snapshot.body[-1] = ast.parse('return _controller.freeze(state, _physical_contract)').body[0]
    # Initialization and FULL integrity are still original and execute once.
    restore = next(n for n in fn.body if isinstance(n, ast.If)
                   and ast.unparse(n.test) == 'checkpoint is not None')
    state_assignment = next(n for n in snapshot.body if isinstance(n, ast.Assign)
                            and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'state')
    names = [k.value for k in state_assignment.value.keys]
    names += ['rejected_trials', 'pending_trial', 'last_trap_state']
    names = list(dict.fromkeys(names))
    need(set(('x','p','q','t','steps','history')) <= set(names), 'complete original physical state names')
    nonlocal_names = [x for x in names if x not in ('recovery','monitor')]
    restore_code = 'def _restore(frame):\n    nonlocal ' + ','.join(nonlocal_names) + '\n'
    restore_code += '    value = _controller.restore(frame)\n'
    for name in nonlocal_names:
        restore_code += f"    {name} = value[{name!r}]\n"
    restore_code += "    if monitor is not None:\n        monitor.__dict__.clear()\n        monitor.__dict__.update(copy.deepcopy(value['monitor']))\n        if monitor.anchor is not None: monitor.anchor = np.asarray(monitor.anchor,float)\n        monitor.contact_ids = tuple(monitor.contact_ids)\n        monitor.load_bearing_ids = tuple(monitor.load_bearing_ids)\n"
    restore_code += "    inertial.set_recovery_mode(value['recovery'])\n"
    restore_fn = ast.parse(restore_code).body[0]
    branch_body = copy.deepcopy(loop.body)
    insertion = next(i for i,n in enumerate(branch_body) if isinstance(n,ast.Assign)
                     and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'accepted')
    base = next(n for n in branch_body if isinstance(n,ast.Assign)
                and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'dt')
    args = [copy.deepcopy(x) for x in base.value.args if ast.unparse(x) != 'horizon - t']
    need(len(args) == len(base.value.args)-1, 'one original horizon cap')
    args.append(ast.parse('relaxation_fraction*tau_rot if rigid_rotation else max_dt',mode='eval').body)
    cap = ast.parse('dt = _controller.select_dt(dt, 0., near, q, a, t, steps)').body[0]
    cap.value.args[1] = ast.Call(ast.Name('min',ast.Load()),args,[])
    branch_body.insert(insertion, cap)
    attempt = next(n for n in branch_body if isinstance(n,ast.For))
    count = 0
    class CountCall(ast.NodeTransformer):
        def visit_Call(self,node):
            nonlocal count
            if isinstance(node.func,ast.Attribute) and node.func.attr == 'inertial_contact_step':
                count += 1
                return ast.copy_location(ast.Call(ast.Attribute(ast.Name('_controller',ast.Load()),'contact_call',ast.Load()),
                    [node.func,*node.args],node.keywords),node)
            return self.generic_visit(node)
    CountCall().visit(attempt);need(count == 1, 'exactly one original physical call site')
    # Prove that removing both additions restores every original loop statement.
    restored = copy.deepcopy(branch_body); del restored[insertion]
    class Uncount(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and node.func.attr == 'contact_call':
                return ast.copy_location(ast.Call(node.args[0],node.args[1:],node.keywords),node)
            return self.generic_visit(node)
    restored = [Uncount().visit(n) for n in restored]
    need(ast.dump(ast.Module(restored,[]),include_attributes=False) == ast.dump(ast.Module(loop.body,[]),include_attributes=False),
         'literal original physical loop AST after removing only control hooks')
    # Replace only administrative returns with a branch completion collector.
    class FinishReturn(ast.NodeTransformer):
        def visit_Return(self,node):
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id == 'finish':
                return ast.copy_location(ast.Return(ast.Call(ast.Attribute(ast.Name('_controller',ast.Load()),'complete',ast.Load()),
                    [node.value,ast.Call(ast.Name('locals',ast.Load()),[],[])],[])),node)
            return node
    branch_try = copy.deepcopy(outer)
    branch_try.body = branch_body + [ast.parse("return finish('present_at_horizon' if t == horizon else 'paused_checkpoint')").body[0]]
    branch_try = FinishReturn().visit(branch_try)
    branch_fn = ast.FunctionDef(name='_advance_branch',args=ast.parse('def x(frame): pass').body[0].args,
        body=[ast.Nonlocal(nonlocal_names),ast.Expr(ast.Call(ast.Name('_restore',ast.Load()),[ast.Name('frame',ast.Load())],[])),branch_try],decorator_list=[])
    # dt/cap request state is held by the controller, never physical globals.
    index = fn.body.index(outer)
    prefix = fn.body[:index]
    prefix += ast.parse("_physical_contract = digest(contract)\nhistory = _controller.start_history(history)\n").body
    prefix += [restore_fn,branch_fn]
    prefix += ast.parse("return _controller.attach(snapshot(), _advance_branch, _physical_contract, _restore)\n").body
    fn.body = prefix
    fn.args.kwonlyargs.append(ast.arg('_controller'));fn.args.kw_defaults.append(None)
    ast.fix_missing_locations(tree)
    ns = dict(namespace)
    exec(compile(tree,str(SELF)+'::original_substep_packet_machine','exec'),ns)
    proof = dict(original_generated_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        original_generated_ast_sha256=token(ast.dump(original,include_attributes=False)),
        original_loop_ast_after_removing_two_hooks_identical=True,
        administrative_changes=['structural snapshot instead of per-trial FULL digest',
            'restore complete small state/monitor/recovery and shared literal history',
            'internal one-original-branch callable; packet loop outside campaign API',
            'branch completion metadata collector'],physical_changes=[],native_calls_during_compile=0)
    return ns['integrate'],proof


def extract_original_scope(function):
    """Retain a frozen wrapper's literal binding prefix/finally, no solve.

    The only nested integration dispatch is replaced by yield. All numerical
    wrappers and their restore clauses retain their original AST/code. The
    omitted suffix only attaches performance counters to the returned result.
    """
    source=inspect.getsource(function);tree=ast.parse(source);fn=tree.body[0]
    index=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Try))
    old=fn.body[index]
    need(len(old.body)==1 and not old.handlers and not old.orelse and old.finalbody,
         'single nested integration inside original binding try/finally')
    assignment=old.body[0]
    need(isinstance(assignment,ast.Assign) and isinstance(assignment.value,ast.Call)
         and getattr(assignment.value.func,'attr',None)=='integrate','exact nested integration dispatch')
    prefix=copy.deepcopy(fn.body[:index]);final=copy.deepcopy(old.finalbody)
    proof=dict(wrapper_source_file=inspect.getsourcefile(function),
        wrapper_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        prefix_ast_sha256=token(ast.dump(ast.Module(prefix,[]),include_attributes=False)),
        finally_ast_sha256=token(ast.dump(ast.Module(final,[]),include_attributes=False)),
        nested_integrate_calls_replaced_by_yield=1,physical_equation_changes=0,
        original_prefix_and_finally_ast_identical=True)
    fn.name='_original_binding_scope';fn.decorator_list=[]
    fn.body=prefix+[ast.Try(body=[ast.Expr(ast.Yield(ast.Name('_scope_proof',ast.Load())))],
        handlers=[],orelse=[],finalbody=final)]
    ast.fix_missing_locations(tree);namespace={**function.__globals__,'_scope_proof':proof}
    exec(compile(tree,str(SELF)+'::literal_original_binding_scope','exec'),namespace)
    return contextmanager(namespace[fn.name]),proof


@contextmanager
def original_inner_execution_scopes(q):
    """Actual inner runtime contexts omitted by direct generated-function use."""
    runtime=q.job.parent.engine.runtime
    observer=runtime.previous
    source104=observer.api.frozen.Runner.integrate.__func__.__globals__['parent']
    source89=source104.h.candidate;source81=source89.parent;source80=source81.parent
    need([Path(x.__file__).parent.name for x in (source104,source89,source81,source80)]
         ==['stage104_staging','stage89_staging','stage81_staging','stage80_staging'],
         'literal original wrapper order and source family')
    modules=(source104,source89,source81,source80)
    scopes=[extract_original_scope(module.integrate) for module in modules]
    legacy=observer.candidate.legacy;saved=legacy.swept_gap
    legacy.swept_gap=observer.candidate.swept_gap
    try:
        with ExitStack() as stack:
            proofs=[stack.enter_context(scope()) for scope,proof in scopes]
            need(source80.contact is q.job.observer.backend,
                 'original Stage80 within-pose live backend matches observed backend')
            yield proofs
    finally:
        need(legacy.swept_gap is observer.candidate.swept_gap,'original Stage117 active sweep binding unchanged')
        legacy.swept_gap=saved


class QualifiedCapture:
    """Use the actual original contact/gap/per-pose scopes, without row replay.

    The owner must install and qualify all original outer runtime scopes. This
    class does not configure or warm native kernels. Original scope assertions
    fail closed when that live stack has not been installed correctly.
    """
    def __init__(self, q, gate):
        self.q, self.gate = q, gate
        self.gaps = importlib.import_module('normal_gap_scope_v1')
        self.trace=None

    @contextmanager
    def packet_scope(self):
        q = self.q
        q.raw.__globals__['clear_telemetry']()
        q.raw.__globals__['fast'].capture_systems=True
        q.job.parent.engine.runtime._calls.clear()
        wrapped = q.observation.__wrapped__
        admin = type('BoundAdmin',(),{'bound':staticmethod(self.gate)})()
        clone = FunctionType(wrapped.__code__,{**wrapped.__globals__,'c':admin},wrapped.__name__,wrapped.__defaults__,wrapped.__closure__)
        need(self.trace is None,'nonreentrant original packet observation')
        try:
            with contextmanager(clone)(q.job.parent.engine.runtime,True) as trace:
                with self.gaps.scope() as gap_log:
                    # Historical production enters observer/kernel BEFORE
                    # runtime repair and Stage104/89/81/80 binding wrappers.
                    # In V1 these wrappers preceded kernel._origins(), so the
                    # legitimate short-PGS/projection bindings were rejected.
                    with q.job.parent.engine.runtime.repair_scope():
                        with original_inner_execution_scopes(q) as inner_proofs:
                            modal=importlib.import_module('reconstruct_fixed_pose_v3').modal
                            need(modal.CANDIDATE.__globals__['geometry_tools'].swept_gap is q.raw.__globals__['prior'].candidate.swept_gap,
                                 'actual original certified sweep bound inside original runtime order')
                            self.inner_proofs=plain(inner_proofs)
                            self.trace,self.gap_log=trace,gap_log
                            yield
        finally:
            self.trace=None

    @contextmanager
    def scope(self,role,before):
        need(self.trace is not None,'original capture is installed once per packet')
        q=self.q;capture=q.observation.__wrapped__.__globals__['old'].ORIGINAL_OBSERVER.old
        runtime=q.job.parent.engine.runtime
        lo,lf=len(capture.fast.attempts),len(capture.capture.records)
        lr,lc,ls=len(capture.fast.old.telemetry),len(runtime._calls),len(q.job.prior.candidate.records)
        lcert=len(q.job.parent.fix.telemetry);lt=len(self.trace['trial_inner_counts'])
        lg=len(self.gap_log['prepare_calls']);ld=len(self.trace['detailed_trials']);data={}
        try:yield data
        finally:
            large={'trial_inner_counts','trial_route_counts','cycle_guard_trials','detailed_trials'}
            trace={k:plain(v) for k,v in self.trace.items() if k not in large}
            for key in ('trial_inner_counts','trial_route_counts','cycle_guard_trials'):
                trace[key]=plain(self.trace[key][lt:])
            trace['detailed_trials']=plain(self.trace['detailed_trials'][ld:])
            for entry in trace['cycle_guard_trials']:entry['trial_index']-=lt
            for trial in trace['detailed_trials']:
                trial['trial_index']-=lt
                for item in (trial,*trial['inner_systems']):
                    item['early_range'] = [x-lo for x in item['early_range']]
                    item['fallback_range'] = [x-lf for x in item['fallback_range']]
            gaps={**{k:plain(v) for k,v in self.gap_log.items() if k!='prepare_calls'},
                  'prepare_calls':plain(self.gap_log['prepare_calls'][lg:])}
            for entry in gaps['prepare_calls']:entry['index']-=lg
            data.update(contact_trial_trace=trace,normal_gap_operand_policy=gaps,
                early_attempts=plain(capture.fast.attempts[lo:]),fallback_systems=plain(capture.capture.records[lf:]),
                repairs=plain(capture.fast.old.telemetry[lr:]),stage119_repair_calls=plain(runtime._calls[lc:]),
                certificates=plain(q.job.parent.fix.telemetry[lcert:]),
                sweep_certificates=plain(q.job.prior.candidate.records[ls:]),
                backend_calls=[dict(enabled=True,backend=str(q.job.observer.backend.__file__),
                    provenance='direct source-verified live namespace binding, not trampoline telemetry')])


def default_source_provider(dispatch_gate):
    """Lazy actual graph import/AST compile only; never configure or warm."""
    for relative, expected in SOURCE_PINS.items():
        need(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected, 'frozen source '+relative)
    reconstruction = importlib.import_module('reconstruct_fixed_pose_v3')
    selector = importlib.import_module('contact_onset_timecap_v1')
    q = reconstruction.s.q
    ns = dict(reconstruction.modal.CANDIDATE.__globals__)
    # This is the live Stage79 backend used by the original checkpoint trampoline,
    # not the stale import-time Stage41 alias (Stage151 v2's documented rule).
    ns['inertial'] = q.job.observer.backend
    return dict(source=reconstruction.modal.GENERATED_SOURCE,namespace=ns,selector=selector,
                capture=QualifiedCapture(q,dispatch_gate),qualified=q)


class Runtime:
    def __init__(self,spec,binding,field,geometry,*,dispatch_gate,capture_factory=None,source_provider=None):
        need(callable(dispatch_gate),'owner-supplied verified numerical authority required; no default grant')
        self.spec,self.binding,self.field,self.geometry=copy.deepcopy(spec),binding,field,geometry
        self.adapter_source_sha256=hashlib.sha256(SELF.read_bytes()).hexdigest()
        self.gate=dispatch_gate
        provider=(source_provider or default_source_provider)(dispatch_gate)
        self.provider=provider;self.selector=provider['selector']
        self.capture=capture_factory or provider['capture']
        namespace=dict(provider['namespace']);original_trap=namespace['trap_event_v2'];Base=original_trap.TrapMonitor
        controller=self
        class ObservedMonitor(Base):
            def update(monitor,interval,position,velocity,contacts,bearing):
                value=super().update(interval,position,velocity,contacts,bearing)
                controller.observe_dwell(interval,position,velocity,contacts,bearing,value)
                return value
        namespace['trap_event_v2']=SimpleNamespace(**{**vars(original_trap),'TrapMonitor':ObservedMonitor})
        self.factory,self.proof=compile_machine(provider['source'],namespace)
        self.proof['monitor_observation']='transparent original update args/result; no checkpoint fields added'
        self.np=provider['namespace']['np']
        self.machine=None;self.frames={};self.store=None;self.current=None;self.active_branch=None

    def _dispatch(self):
        value=self.gate()
        need(isinstance(value,dict) and value.get('native_dispatch_authorized') is True,
             'native dispatch has separately verified fresh owner authority')
        need(time.time()<self.time_bound,'bounded packet native cutoff')
        return value

    def start_history(self,literal):
        self.store=HistoryStore(literal,self.history_descriptor)
        # Original full input hash was authenticated by original initialization.
        return self.store.start(self.input_full_sha)

    def freeze(self,state,contract):
        history=state['history'];need(isinstance(history,History),'structurally shared original history')
        header=plain({k:v for k,v in state.items() if k!='history'})
        header.update(history_node=history.node,history_length=history.store.nodes[history.node]['length'])
        parent=self.current['token'] if self.current is not None else self.initial_token
        delta=[] if self.current is None else history.store.suffix(history.node,self.current['state']['history_node'])
        identity=state_token(parent,header,delta)
        frame=dict(token=identity,parent=parent,state=header,history_delta=delta,contract=contract)
        need(identity not in self.frames or self.frames[identity]==frame,'same logical state token')
        self.frames[identity]=frame
        return frame

    def restore(self,frame):
        need(frame['token'] in self.frames and self.frames[frame['token']]==frame,'owned immutable logical state')
        value=copy.deepcopy(frame['state']);node=value.pop('history_node');value.pop('history_length')
        value['history']=History(self.store,node)
        for name in ('x','p','q'):value[name]=self.np.asarray(value[name],float).copy()
        return value

    def attach(self,initial,advance,contract,restore_machine):
        self.initial,self.advance,self.contract=initial,advance,contract
        self.restore_machine=restore_machine
        return self

    def select_dt(self,base,full,near,q,a,t,steps):
        branch=self.active_branch
        requested=branch['requested_dt_s'];target=branch['target_time_s']
        speed=self.spec['config']['target_mean_interstitial_velocity_m_s']
        selected,ids=self.selector.select(base,near,q,a,speed,untruncated_dt=full)
        actual=selected if branch.get('nominal_smoke_passthrough') else min(selected,requested,target-t)
        need(math.isfinite(actual) and actual>0,'positive requested physical interval')
        branch['cap_entries'].append(dict(time_s=float(t),steps=int(steps),velocity_generalized=plain(q),
            near=[[int(c[0]),float(c[1]),plain(c[2]),plain(c[3])] for c in near],base_dt_s=float(base),
            untruncated_dt_s=float(full),original_selected_dt_s=float(selected),requested_dt_s=requested,
            target_time_s=target,actual_trial_dt_s=float(actual),trigger_grain_ids=ids))
        return actual

    def contact_call(self,original,*args,**kwargs):
        self._dispatch()
        need(self.packet_work < self.max_work,'all shadow/fine/rejected trial work-row cap')
        self.packet_work+=1;self.active_branch['work_rows']+=1
        return original(*args,**kwargs)

    def observe_dwell(self,interval,position,velocity,contacts,bearing,value):
        need(self.active_branch is not None,'dwell observation belongs to an actual original branch')
        self.active_branch['dwell_calls'].append(dict(dt_s=interval,position_m=plain(position),
            velocity_generalized=plain(velocity),active_contact_ids=plain(contacts),
            supported_bearing_ids=plain(bearing),dwell=plain(value)))

    def complete(self,result,local):
        branch=self.active_branch;after=result['checkpoint'];before=self.current
        branch['output_state_token']=after['token'];branch['after_state']=after['state']
        branch['history_delta']=after['history_delta'];branch['result_status']=result['status']
        branch['result_reason']=result.get('reason');branch['compact_result']={k:plain(v) for k,v in result.items() if k not in ('checkpoint','history')}
        branch['rows']=[];branch['sweep_certificates']=[]
        if after['state']['steps']==before['state']['steps']+1:
            s=after['state'];active=local['active']
            dt=local['event'] if result['status']=='full_window_exit' else local['dt']
            need(len(branch['dwell_calls'])==1,'one exact original interval dwell observation per accepted row')
            dwell=branch['dwell_calls'][0]
            need(dwell['dt_s']==dt and dwell['position_m']==s['x'] and dwell['velocity_generalized']==s['q']
                 and dwell['active_contact_ids']==[int(c[0]) for c in active] and dwell['dwell']==s['last_trap_state'],
                 'literal original dwell args/result bound to accepted physical state')
            branch['rows']=[dict(time_s=s['t'],dt_s=dt,position_m=s['x'],orientation=s['p'],
                velocity_generalized=s['q'],active_contact_ids=[int(c[0]) for c in active],
                supported_bearing_ids=dwell['supported_bearing_ids'],
                dwell=s['last_trap_state'])]
            branch['sweep_certificates']=[dict(dt_s=float(local['dt']),certified=False,reference_gap_m=float(local['swept_gap']))]
        need(after['state']['steps']-before['state']['steps'] in (0,1),'one literal original accepted substep')
        return after

    def _initialize(self,checkpoint):
        outer=checkpoint
        validate_outer_checkpoint_admission(outer,self.limits.numerical_binding,self.adapter_source_sha256)
        if outer is not None:
            need(outer.get('schema')==CHECKPOINT_SCHEMA
                 and outer.get('adapter_source_sha256')==self.adapter_source_sha256
                 and outer.get('limits_sha256')==token(asdict(self.limits))
                 and outer.get('spec_sha256')==original_digest(self.spec)
                 and outer.get('physical_binding')==self.binding,
                 'only a source/policy-bound new-controller checkpoint; no old bare checkpoint credit')
        cp=None if outer is None else outer['physical_checkpoint']
        self.input_full_sha=original_digest(cp)
        self.initial_token=token(dict(kind='packet-boundary-original-FULL',sha256=self.input_full_sha))
        self.history_descriptor=None if outer is None else outer['history_root']
        self.current=None;self.frames={}
        cfg=self.spec['config'];a,b,_=cfg['prolate_semiaxes_m'];n=cfg['numerics'];start=self.spec['initial_state']
        self.factory(self.field,self.geometry,start['position_m'],start['orientation'],start['velocity_generalized'],
            a,b,cfg['dynamic_viscosity_Pa_s'],cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],
            cfg['gravity_m_s2'],cfg['friction_coefficient'],self.spec['field_metadata']['cell_length_m'],self.spec['horizon_s'],
            added_mass_fraction=cfg['added_mass_fraction'],cutoff_ratio=.2,roughness_ratio=.01,
            displacement_fraction=n['displacement_fraction'],angle_limit=n['angle_limit_rad'],
            relaxation_fraction=n['relaxation_fraction'],max_dt=n['max_dt_s'],max_steps=2**53,
            wall_budget=max(.001,self.time_bound-time.time()),trap_reference_speed=cfg['target_mean_interstitial_velocity_m_s'],
            trap_dwell_time=cfg['trap']['dwell_time_s'],trap_speed_ratio=cfg['trap']['speed_ratio'],
            trap_drift_over_minor_radius=cfg['trap']['drift_over_minor_radius'],stop_on_trap=cfg['trap']['absorbing'],
            reynolds_limit=n['reynolds_limit'],checkpoint=cp,checkpoint_binding=self.binding,pause_after_steps=None,
            rigid_rotation=True,_controller=self)
        if outer:
            todo=copy.deepcopy(outer['staged_history_nodes'])
            while todo:
                ready=[k for k,v in todo.items() if v['parent'] in self.store.nodes]
                need(ready,'bounded acyclic staged history nodes')
                for node in ready:
                    value=todo.pop(node)
                    if node not in self.store.nodes:self.store.add(node,value['parent'],value['delta'])
                    else:need(self.store.nodes[node]==value,'no ignored conflicting staged history data')
            self.frames=copy.deepcopy(outer['frames'])
            for identity,frame in self.frames.items():
                state=frame['state']
                need(identity==frame['token']==state_token(frame['parent'],state,frame['history_delta'])
                     and frame['contract']==cp['contract'] and state['history_node'] in self.store.nodes
                     and state['history_length']==self.store.nodes[state['history_node']]['length'],
                     'complete literal staged frame token/contract/history binding before force')
            self.current=self.frames[outer['published_state_token']]
            need(self.current['state']['t']==cp['state']['t'] and self.materialize(self.current)==cp,
                 'outer controller checkpoint authenticates exact original FULL state')
            self.cursor=copy.deepcopy(outer['cursor']);self.totals=copy.deepcopy(outer['numeric_ledger'])
            self.carried=copy.deepcopy(outer.get('pending_branches',[]))
        else:
            self.current=self.initial;self.cursor=dict(phase='idle',macro_index=0,trial_index=0,
                origin_state_token=self.initial['token'],h_s=None,original_selected_cap_s=None,depth=0,
                branch_ids=[],decision=None,published_half_count=0,pending_branch_id=None)
            self.totals=dict(all_work_rows=0,accepted_half_rows=0,rejected_trials=0)
            self.carried=[]

    def materialize(self,frame):
        state=copy.deepcopy(frame['state']);node=state.pop('history_node');state.pop('history_length')
        state['history']=self.store.materialize(node)
        return dict(schema=1,contract=frame['contract'],state=state,state_sha256=original_digest(state))

    def _branch(self,role,origin,h,target):
        self._dispatch();published=self.current;self.current=origin
        index=f"m{self.cursor['macro_index']:09d}_t{self.cursor['trial_index']:09d}_{role}"
        branch=dict(branch_id=index,macro_index=self.cursor['macro_index'],role=role,
            contract=origin['contract'],
            nominal_smoke_passthrough=getattr(self,'nominal_smoke_passthrough',False),
            input_state_token=origin['token'],before_state=copy.deepcopy(origin['state']),
            history_parent=origin['token'],history_delta=[],cap_entries=[],dwell_calls=[],rows=[],sweep_certificates=[],
            requested_dt_s=h,target_time_s=target,work_rows=0,error=None)
        self.active_branch=branch
        try:
            with self.capture.scope(role,origin['state']) as evidence:
                after=self.advance(origin)
            branch.update(plain(evidence))
            need(after['state']['rejected']==origin['state']['rejected']
                 and after['state']['pending_trial'] is None and len(branch['rows'])==1,
                 'original zero-rejection/complete-row physical policy; failures remain charged')
            need(branch['result_status'] in ('paused_checkpoint','present_at_horizon','full_window_exit'),
                 'original physical failure stops, never an accuracy retry')
        except Exception as exc:
            branch['error']=repr(exc);branch['result_status']='native_or_capture_failure'
            if 'evidence' in locals():branch.update(plain(evidence))
            self.branches.append(branch)
            raise
        finally:
            self.current=published
            self.restore_machine(published)
        self.branches.append(branch)
        return branch,after

    def _original_cap(self,origin):
        # Assembly only. No force, advancement or history call is performed.
        assemble=self.provider.get('assemble')
        if assemble is None:
            reconstruction=importlib.import_module('reconstruct_fixed_pose_v3');assemble=reconstruction.ASSEMBLE
        s=origin['state'];cfg=self.spec['config'];n=cfg['numerics'];a,b,_=cfg['prolate_semiaxes_m']
        args=assemble(self.field,self.geometry,self.np.asarray(s['x']),self.np.asarray(s['p']),self.np.asarray(s['q']),
            a,b,cfg['dynamic_viscosity_Pa_s'],cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],cfg['gravity_m_s2'],
            cfg['friction_coefficient'],math.inf,s['t'],cfg['added_mass_fraction'],.2,.01,
            n['displacement_fraction'],n['angle_limit_rad'],n['relaxation_fraction'],n['max_dt_s'],n['reynolds_limit'])
        full=float(args[8]);base=min(full,self.spec['horizon_s']-s['t'])
        near=self.provider['namespace']['enrich'](self.geometry,self.geometry.contacts(self.np.asarray(s['x']),
            self.np.asarray(s['p']),a,b,.2*float(self.np.max(self.geometry.r))))
        return self.selector.select(base,near,self.np.asarray(s['q']),a,cfg['target_mean_interstitial_velocity_m_s'],
                                    untruncated_dt=full)[0]

    def advance_packet(self,checkpoint,limits,*,max_work_rows=5000,pause_after_accepted_rows=None,
                       pause_after_time_s=None,time_bound,record_id,pause_at_phase=None,
                       previous_packet_receipt_sha256=None):
        scope=getattr(self.capture,'packet_scope',nullcontext)
        with scope():
            if hasattr(self.capture,'inner_proofs'):
                self.proof['original_inner_scope_proofs']=plain(self.capture.inner_proofs)
            return self._advance_packet(checkpoint,limits,max_work_rows=max_work_rows,
                pause_after_accepted_rows=pause_after_accepted_rows,pause_after_time_s=pause_after_time_s,
                time_bound=time_bound,record_id=record_id,pause_at_phase=pause_at_phase,
                previous_packet_receipt_sha256=previous_packet_receipt_sha256)

    def _advance_packet(self,checkpoint,limits,*,max_work_rows=5000,pause_after_accepted_rows=None,
                        pause_after_time_s=None,time_bound,record_id,pause_at_phase=None,
                        previous_packet_receipt_sha256=None):
        """One bounded native record; all branches retained, no disk writes."""
        limits.validate();need(type(max_work_rows)is int and 0<max_work_rows<=5000,'work packet cap')
        need(pause_after_accepted_rows is None or type(pause_after_accepted_rows)is int
             and pause_after_accepted_rows>0,'positive accepted-row pause')
        need(pause_after_time_s is None or math.isfinite(pause_after_time_s)
             and pause_after_time_s>0,'finite positive administrative physical-clock pause')
        self.pause_after_time_s=pause_after_time_s
        need(isinstance(record_id,str) and record_id,'owner integration record identity')
        need(pause_at_phase in (None,'C_done','F1_done','F2_done','decision_done'),
             'explicit bounded diagnostic phase pause only')
        self.time_bound=float(time_bound);self.max_work=max_work_rows;self.packet_work=0;self.limits=limits
        self.branches=[];self.trials=[];self.committed=[];self.accepted=[];self.carried_out=[]
        self._dispatch();self._initialize(checkpoint)
        input_token=self.current['token'];cursor_before=copy.deepcopy(self.cursor);ledger_before=copy.deepcopy(self.totals)
        input_state=copy.deepcopy(self.current['state'])
        input_history_nodes=set(self.store.nodes)
        if self.carried:
            need(isinstance(previous_packet_receipt_sha256,str) and len(previous_packet_receipt_sha256)==64,
                 'staged branches require the actual prior packet receipt identity')
            self.carried_out=copy.deepcopy(self.carried)
            for branch in self.carried_out:branch['previous_packet_receipt_sha256']=previous_packet_receipt_sha256
        status,error='paused_controller',None
        try:
            while self.current['state']['t']<self.spec['horizon_s']:
                self._dispatch()
                phase=self.cursor['phase']
                if phase=='publish_second_half':
                    branch=next(b for b in self.carried if b['branch_id']==self.cursor['pending_branch_id'])
                    self._publish(branch);self._idle()
                    if self._pause(pause_after_accepted_rows):break
                    continue
                if phase=='terminal_negative':raise Stop('negative cursor cannot resume dispatch')
                if phase=='idle':
                    if self.packet_work+3>self.max_work:break
                    original_cap=self._original_cap(self.current)
                    clock=choose_clock_interval(self.current['state']['t'],original_cap,limits.minimum_h_s,limits.maximum_halvings)
                    self.cursor.update(macro_index=self.cursor['macro_index']+1,trial_index=0,
                        origin_state_token=self.current['token'],h_s=clock['h_s'],clock_preflight=clock,
                        original_selected_cap_s=original_cap,depth=0,branch_ids=[],
                        decision=None,published_half_count=0)
                origin=self.frames[self.cursor['origin_state_token']]
                h,depth=self.cursor['h_s'],self.cursor['depth'];t=origin['state']['t']
                need(limits.minimum_h_s<=h<=self.cursor['original_selected_cap_s'],'finite original cap')
                split=choose_clock_interval(t,h,limits.minimum_h_s,limits.maximum_halvings)
                roles=('C','F1','F2')
                if pause_at_phase is None and not self.cursor['branch_ids'] and self.packet_work+3>self.max_work:break
                for role in roles[len(self.cursor['branch_ids']):]:
                    if self.packet_work>=self.max_work:break
                    before=origin if role!='F2' else self.frames[self._find_branch(self.cursor['branch_ids'][1])['output_state_token']]
                    interval=h if role=='C' else split['first_interval_s'] if role=='F1' else split['second_interval_s']
                    target=split['midpoint_time_s'] if role=='F1' else split['end_time_s']
                    branch,after=self._branch(role,before,interval,target)
                    self.cursor['branch_ids'].append(branch['branch_id'])
                    self.cursor['phase']={'C':'after_coarse','F1':'after_first_half','F2':'after_second_half'}[role]
                    if branch['result_status']=='full_window_exit':
                        raise Stop('Original export preserved; terminal comparison is not qualified. No extension, alignment or export promotion.')
                    if pause_at_phase=={'C':'C_done','F1':'F1_done','F2':'F2_done'}[role]:
                        break
                if pause_at_phase in ('C_done','F1_done','F2_done') and self.cursor['phase']=={
                    'C_done':'after_coarse','F1_done':'after_first_half','F2_done':'after_second_half'}[pause_at_phase]:break
                if len(self.cursor['branch_ids'])<3:break
                bs=[self._find_branch(x) for x in self.cursor['branch_ids']]
                fs=[self.frames[x['output_state_token']] for x in bs]
                # An original cap at F1/F2 can be below the proposed half. Such
                # an incomplete interval is NOT silently called step doubling.
                already_decided=self.cursor['phase']=='after_decision'
                if already_decided:decision=self.cursor['decision']
                else:
                    try:
                        decision=decision_values(limits,origin,*fs,h,self.cursor['original_selected_cap_s'],depth)
                    except Stop as exc:
                        if 'exact common clock' not in str(exc):raise
                        need(depth<limits.maximum_halvings and h/2>=limits.minimum_h_s,'half cap mismatch exhausted finite retries')
                        decision=dict(action='discard_all_and_halve',reason='cap_mismatch',
                            position_defect_m=None,director_defect=None,velocity_defect_over_U=None,scaled_defect=None,
                            next_h_s=h/2,next_halving_depth=depth+1,committed_state_token=None,
                            witness_semantics='controller_state_token_not_original_FULL_sha')
                    self.cursor['decision']=decision;self.cursor['phase']='after_decision'
                    self.trials.append(dict(macro_index=self.cursor['macro_index'],trial_index=self.cursor['trial_index'],depth=depth,
                        h_s=h,original_selected_cap_s=self.cursor['original_selected_cap_s'],origin_state_token=origin['token'],
                        clock_preflight=copy.deepcopy(split),
                        branch_ids=list(self.cursor['branch_ids']),decision=copy.deepcopy(decision)))
                if pause_at_phase=='decision_done':break
                if decision['action']=='discard_all_and_halve':
                    self.current=origin;self.totals['rejected_trials']+=1
                    self.cursor.update(phase='after_rejection',h_s=h/2,depth=depth+1,
                        trial_index=self.cursor['trial_index']+1,branch_ids=[],decision=None)
                    continue
                self.current=origin
                self._publish(bs[1])
                if self._pause(pause_after_accepted_rows,include_time=False):
                    self.cursor.update(phase='publish_second_half',pending_branch_id=bs[2]['branch_id'],published_half_count=1)
                    self.carried=[copy.deepcopy(x) for x in bs];break
                self._publish(bs[2]);self._idle()
                if self._pause(pause_after_accepted_rows):break
            if self.current['state']['t']==self.spec['horizon_s']:status='present_at_horizon'
        except Exception as exc:
            status='negative';error=repr(exc);self.cursor['phase']='terminal_negative'
        self.totals['all_work_rows']+=self.packet_work
        cp=self.materialize(self.current)
        pending_ids=self.cursor['branch_ids'] if self.cursor['phase']!='idle' else []
        pending=[copy.deepcopy(self._find_branch(k)) for k in pending_ids]
        required={self.current['token'],self.cursor['origin_state_token']}
        for branch in pending:
            required.add(branch['input_state_token'])
            if 'output_state_token' in branch:required.add(branch['output_state_token'])
        staged={k:copy.deepcopy(self.frames[k]) for k in required if k in self.frames}
        envelope=dict(schema=CHECKPOINT_SCHEMA,physical_checkpoint=cp,published_state_token=self.current['token'],
            adapter_source_sha256=self.adapter_source_sha256,limits_sha256=token(asdict(limits)),
            policy_sha256=limits.numerical_binding,
            spec_sha256=original_digest(self.spec),physical_binding=self.binding,
            history_root=self.store.descriptor,staged_history_nodes={k:plain(v) for k,v in self.store.nodes.items()
                if k!=self.store.root and k not in self._published_history_nodes()},
            frames=staged,cursor=copy.deepcopy(self.cursor),
            numeric_ledger=copy.deepcopy(self.totals),pending_branches=pending)
        packet=dict(schema=SCHEMA,record_id=record_id,status=status,error=error,source_proof=self.proof,
            input_state=input_state,limits=asdict(limits),policy_sha256=limits.numerical_binding,
            input_state_token=input_token,output_state_token=self.current['token'],work_branches=plain(self.branches),
            carried_branches=plain(self.carried_out),trials=plain(self.trials),committed_branch_ids=list(self.committed),
            accepted_rows=plain(self.accepted),state_headers={k:v['state'] for k,v in self.frames.items()},
            history_nodes={k:plain(v) for k,v in self.store.nodes.items() if k not in input_history_nodes},
            input_history_node=self.frames[input_token]['state']['history_node'],
            cursor_before=cursor_before,cursor_after=copy.deepcopy(self.cursor),
            ledger_before=ledger_before,ledger_after=copy.deepcopy(self.totals),
            reservation=dict(record_id=record_id,maximum_work_rows=max_work_rows),work_rows=self.packet_work,
            original_FULL_input_sha256=self.input_full_sha,original_FULL_output_sha256=original_digest(cp),
            input_full_checkpoint_sha256=self.input_full_sha,output_full_checkpoint_sha256=original_digest(cp),
            checkpoint=envelope,original_FULL_auditor_replayed_per_trial=False,
            native_qualification_claimed=False,core_result_admitted=False)
        return packet

    def _published_history_nodes(self):
        result=set();node=self.current['state']['history_node']
        while node is not None:
            result.add(node);node=self.store.nodes[node]['parent']
        return result

    def _find_branch(self,identity):
        return next(b for b in (*self.branches,*self.carried) if b['branch_id']==identity)

    def _publish(self,branch):
        need(branch['role'] in ('F1','F2') and branch['input_state_token']==self.current['token'],
             'only contiguous literal fine halves can be published')
        self.current=self.frames[branch['output_state_token']]
        self.committed.append(branch['branch_id']);self.accepted.extend(branch['rows'])
        self.totals['accepted_half_rows']+=len(branch['rows'])

    def _pause(self,maximum,include_time=True):
        return (maximum is not None and len(self.accepted)>=maximum
                or include_time and self.pause_after_time_s is not None and self.current['state']['t']>=self.pause_after_time_s)

    def _idle(self):
        self.cursor.update(phase='idle',origin_state_token=self.current['token'],h_s=None,
            original_selected_cap_s=None,depth=0,branch_ids=[],decision=None,
            clock_preflight=None,
            pending_branch_id=None,published_half_count=2)


def build_runtime(spec,binding,field,geometry,*,dispatch_gate,capture_factory=None,source_provider=None):
    return Runtime(spec,binding,field,geometry,dispatch_gate=dispatch_gate,
                   capture_factory=capture_factory,source_provider=source_provider)


def native_stack_prelude(dispatch_gate):
    """Explicit future standalone setup request, never an implicit scope side effect."""
    grant=dispatch_gate()
    need(grant.get('native_dispatch_authorized') is True and grant.get('native_prelude_authorized') is True,
         'separately registered native arithmetic prelude request')
    for relative,expected in SOURCE_PINS.items():
        need(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,'frozen prelude source '+relative)
    reconstruction=importlib.import_module('reconstruct_fixed_pose_v3');q=reconstruction.s.q
    cutoff=datetime.fromisoformat(grant['simulation_cutoff_utc']).timestamp()
    need(time.time()<cutoff,'original owner prelude cutoff')
    candidate=q.baseline.execute.__globals__['frozen'].execute.__globals__['candidate']
    configure=q.reference.JOB.parent.b.old.parent.configure;hot=configure.__globals__['hot']
    original_phase=hot.phase;backend=q.job.observer.backend;original_outer=backend.inertial_contact_step
    phases=[0];outer_calls=[0];started=time.perf_counter()
    def observed_phase(*args,**kwargs):
        phases[0]+=1;need(phases[0]<=2,'exact original synthetic warm invocation envelope')
        return original_phase(*args,**kwargs)
    def forbidden_outer(*args,**kwargs):
        outer_calls[0]+=1
        raise Stop('Synthetic stack prelude must never advance an outer transport trial')
    hot.phase=observed_phase;backend.inertial_contact_step=forbidden_outer
    try:
        configure();candidate.warm();residual=q.kernel.warm();q.kernel.reset()
    finally:
        exact=(hot.phase is observed_phase and backend.inertial_contact_step is forbidden_outer)
        hot.phase=original_phase;backend.inertial_contact_step=original_outer
        need(exact,'prelude original callable binding restored exactly')
    need(phases[0]==2 and outer_calls[0]==0,'two explicit synthetic contact kernels; no target outer transport')
    need(residual['contact_solver_calls']==residual['outer_calls']==0,
         'residual arithmetic prelude contains no force/transport solve')
    return dict(status='original synthetic stack warm completed; native qualification pending',
        residual_callback_warm=residual,configure_source=inspect.getsourcefile(configure),
        composed_arithmetic_warm_source=str(candidate.__file__),elapsed_s=time.perf_counter()-started,
        nonadvancing_contact_kernel_invocations=phases[0],target_outer_transport_calls=outer_calls[0],
        warm_source_sha256=hashlib.sha256(inspect.getsource(hot.warmup).encode()).hexdigest(),
        observation_return_values_unchanged=True,integration_records=1,saved_work_rows=0,
        particle_steps=0,original_checkpoint_credit=False,native_qualification_passed=False)


@contextmanager
def native_execution_scope(spec,binding,dispatch_gate,*,plan_path,auth_path,physical_path,numerical=True,
                           prior_receipt_authenticator=None):
    """Exact original native scope stack; NEVER entered by source controls.

    The future owner authenticates fresh design/approval/time/source mappings
    before this call and supervises its wall budget. Original warm routines
    compile synthetic arithmetic; they are explicitly reported as prelude,
    not disguised as accepted particle work. No real transport warm call or
    old checkpoint rebinding is performed. Native bit/restart qualification
    and independent composition audit still gate every publication.
    """
    grant=dispatch_gate()
    need(type(numerical)is bool,'explicit native versus read-only audit scope')
    need(grant.get('native_dispatch_authorized') is True if numerical else grant.get('read_only_audit_authorized') is True,
         'explicit current owner scope authority')
    for key,path in (('plan',plan_path),('authorization',auth_path),('physical',physical_path)):
        need(Path(path).is_file(),'owner fixed '+key+' input exists')
    reconstruction=importlib.import_module('reconstruct_fixed_pose_v3')
    s=reconstruction.s;q=s.q;raw=q.raw.__globals__;native=raw['parent'].engine.runtime
    outer=q.baseline.execute.__globals__['frozen'].execute
    need(outer.__code__.co_filename.endswith('stage202_staging\\contact_repaired_stack_preflight_v1.py'),
         'actual original Stage202 outer numerical scope source')
    deps=outer.__globals__;candidate,repair=deps['candidate'],deps['repair']
    original_repair=deps['previous'].baseline.repair
    cutoff=grant['simulation_cutoff_utc'];epoch=datetime.fromisoformat(cutoff).timestamp()
    if numerical:
        need(time.time()<epoch and grant.get('native_stack_prelude_authenticated') is True,
             'fresh native cutoff and separately authenticated explicit arithmetic setup')
        need(q.kernel._SOURCE_VALIDATED and q.kernel._TEMPLATES is not None,
             'actual original callback templates already initialized by registered prelude')
    cfg=spec['config'];metadata=spec['field_metadata']
    with ExitStack() as stack:
        stack.enter_context(s.context.fields.scope(s.api,(spec['seed'],spec['flow_factor'],spec['cpd']),metadata))
        field,data,actual=s.api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
        need(actual==metadata,'exact immutable original field metadata')
        geometry=s.api.frozen.h.geometry_exact_v1.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],actual['cell_length_m'])
        # The order is the original Stage202 outer composition then the original
        # raw inner contexts. Per-pose observer/kernel/gap contexts are entered
        # exactly once per packet by QualifiedCapture.packet_scope().
        runtime=None
        if numerical:
            stack.enter_context(repair.scope(native,True,epoch))
            stack.enter_context(candidate.scope('compiled_direct'))
            stack.enter_context(original_repair.scope(native,True,epoch))
            stack.enter_context(raw['prior'].p.hot.scope())
            stack.enter_context(raw['parent'].fix.scope())
            stack.enter_context(raw['deadline'].scope(native,cutoff,True))
            stack.enter_context(raw['capture'].scope(native,True))
            stack.enter_context(raw['prior'].candidate.scope())
            runtime=build_runtime(spec,binding,field,geometry,dispatch_gate=dispatch_gate)
            need(runtime.provider['namespace']['inertial'] is q.job.observer.backend,
                 'original compiler uses actual live observed contact backend')
            runtime.proof['scope_order_repair']=dict(preserved_v1_sha256=SOURCE_PINS['paper1_staging/full_state_integration_adapter_v1.py'],
                original_observer_kernel_before_runtime_and_inner_bindings=True,
                physical_equation_changes=0,native_qualification_claimed=False)
        physical=json.loads(Path(physical_path).read_text(encoding='utf-8-sig'))
        audit=importlib.import_module('audit_full_state_stepdoubling_v1')
        stencil=audit.create_original_mechanical_adapter(spec,binding,geometry,
            hashlib.sha256(Path(physical_path).read_bytes()).hexdigest(),physical['minimum_gap_semantics'],field=field,
            prior_receipt_authenticator=prior_receipt_authenticator)
        yield dict(runtime=runtime,field=field,geometry=geometry,
            mechanical_stencil_adapter=stencil,original_digest=original_digest,
            source_bindings={str(SELF):hashlib.sha256(SELF.read_bytes()).hexdigest(),
                **{str(ROOT/k):v for k,v in SOURCE_PINS.items()},**stencil.source_files},
            native_setup_force_calls=0,native_qualification_claimed=False)


def materialize_checkpoint(packet):
    return copy.deepcopy(packet['checkpoint']['physical_checkpoint'])


def controller_checkpoint(packet):
    return copy.deepcopy(packet['checkpoint'])


def _smoke_arguments(runtime,checkpoint=None,pause=32):
    spec=runtime.spec;cfg=spec['config'];n=cfg['numerics'];start=spec['initial_state'];aa,bb,_=cfg['prolate_semiaxes_m']
    args=(runtime.field,runtime.geometry,start['position_m'],start['orientation'],start['velocity_generalized'],
        aa,bb,cfg['dynamic_viscosity_Pa_s'],cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],cfg['gravity_m_s2'],
        cfg['friction_coefficient'],spec['field_metadata']['cell_length_m'],spec['horizon_s'])
    kwargs=dict(added_mass_fraction=cfg['added_mass_fraction'],cutoff_ratio=.2,roughness_ratio=.01,
        displacement_fraction=n['displacement_fraction'],angle_limit=n['angle_limit_rad'],
        relaxation_fraction=n['relaxation_fraction'],max_dt=n['max_dt_s'],max_steps=2**53,
        wall_budget=max(.001,runtime.time_bound-time.time()),trap_reference_speed=cfg['target_mean_interstitial_velocity_m_s'],
        trap_dwell_time=cfg['trap']['dwell_time_s'],trap_speed_ratio=cfg['trap']['speed_ratio'],
        trap_drift_over_minor_radius=cfg['trap']['drift_over_minor_radius'],stop_on_trap=cfg['trap']['absorbing'],
        reynolds_limit=n['reynolds_limit'],checkpoint=checkpoint,checkpoint_binding=runtime.binding,
        pause_after_steps=pause,rigid_rotation=True)
    return args,kwargs


def _combine_smoke_observations(branches):
    """Losslessly reindex original branch observation ranges into one record."""
    first=branches[0]['contact_trial_trace']
    large={'trial_inner_counts','trial_route_counts','cycle_guard_trials','detailed_trials'}
    trace={k:plain(v) for k,v in first.items() if k not in large}
    for key in large:trace[key]=[]
    early=[];fallback=[];repairs=[];calls=[];certs=[];proofs=[];gaps=None
    for index,branch in enumerate(branches):
        lo,lf=len(early),len(fallback);source=branch['contact_trial_trace']
        for key in ('trial_inner_counts','trial_route_counts'):trace[key].extend(plain(source[key]))
        for value in plain(source['cycle_guard_trials']):
            value['trial_index']+=index;trace['cycle_guard_trials'].append(value)
        for value in plain(source['detailed_trials']):
            value['trial_index']+=index
            for item in (value,*value['inner_systems']):
                item['early_range']=[x+lo for x in item['early_range']]
                item['fallback_range']=[x+lf for x in item['fallback_range']]
            trace['detailed_trials'].append(value)
        log=branch['normal_gap_operand_policy']
        if gaps is None:gaps={**{k:plain(v) for k,v in log.items() if k!='prepare_calls'},'prepare_calls':[]}
        for value in plain(log['prepare_calls']):
            value['index']+=index;gaps['prepare_calls'].append(value)
        early.extend(plain(branch['early_attempts']));fallback.extend(plain(branch['fallback_systems']))
        repairs.extend(plain(branch['repairs']));calls.extend(plain(branch['stage119_repair_calls']))
        certs.extend(plain(branch['certificates']));proofs.extend(plain(branch['sweep_certificates']))
    return dict(contact_trial_trace=trace,normal_gap_operand_policy=gaps,early_attempts=early,
        fallback_systems=fallback,repairs=repairs,stage119_repair_calls=calls,certificates=certs,
        sweep_certificates=proofs,backend_calls=plain(branches[0]['backend_calls']))


def _native_smoke(runtime,limits,mode,design_sha256,gap_semantics,numerical_contract_sha256,*,rows=32):
    """Internal smoke implementation; fake fixtures supply fake physical calls."""
    need(mode in ('original','compiled') and rows==32,'exact standalone old-bit32 diagnostic only')
    limits.validate();runtime.limits=limits;runtime.time_bound=min(time.time()+45,
        datetime.fromisoformat(runtime.gate()['simulation_cutoff_utc']).timestamp())
    runtime.max_work=rows;runtime.packet_work=0;runtime.branches=[];runtime.trials=[]
    runtime.committed=[];runtime.accepted=[];runtime.carried=[];runtime.carried_out=[]
    native=runtime.provider['namespace']['inertial'];recovery=native.recovery_mode()
    scope=getattr(runtime.capture,'packet_scope',nullcontext)
    source_proof={};journal=[];evidence={};observed=[]
    try:
        runtime._dispatch()
        with scope():
            if mode=='compiled':
                runtime._initialize(None);runtime.nominal_smoke_passthrough=True
                for index in range(rows):
                    runtime.cursor.update(macro_index=index+1,trial_index=0)
                    h=runtime._original_cap(runtime.current)
                    branch,after=runtime._branch('C',runtime.current,h,runtime.current['state']['t']+h)
                    need(branch['result_status']=='paused_checkpoint','smoke cannot stop at an event or horizon')
                    runtime.current=after;runtime.restore_machine(after);observed.extend(branch['rows'])
                cp=runtime.materialize(runtime.current)
                result={**runtime.branches[-1]['compact_result'],'checkpoint':cp,'history':cp['state']['history']}
                evidence=_combine_smoke_observations(runtime.branches)
                journal=[entry for branch in runtime.branches for entry in branch['cap_entries']]
                source_proof={**runtime.proof,'compiled_C_only_no_halves':True,
                    'literal_original_selector_dt_passthrough':True,'production_controller_checkpoint_emitted':False}
            else:
                # The reference is the existing old selector compiler, not the
                # packet machine. Transparent namespace observers preserve its
                # original arithmetic/returned pose/monitor state bit for bit.
                selector=importlib.import_module('contact_onset_timecap_v1')
                candidate,proof=selector.compile_candidate(journal,runtime.spec['config']['target_mean_interstitial_velocity_m_s'])
                need(proof['original_source_digest']==hashlib.sha256(runtime.provider['source'].encode()).hexdigest(),
                     'original nominal smoke exact generated source')
                namespace={**candidate.__globals__,**runtime.provider['namespace']}
                original_mechanics=runtime.provider['namespace']['mechanics'];pose=[None];clock=[0.]
                def advance(*args,**kwargs):
                    value=original_mechanics.advance_pose(*args,**kwargs);pose[0]=value
                    return value
                namespace['mechanics']=SimpleNamespace(**{**vars(original_mechanics),'advance_pose':advance})
                original_trap=runtime.provider['namespace']['trap_event_v2'];Base=original_trap.TrapMonitor
                class ObservedMonitor(Base):
                    def update(self,interval,position,velocity,contacts,bearing):
                        value=super().update(interval,position,velocity,contacts,bearing)
                        clock[0]+=interval
                        observed.append(dict(time_s=clock[0],dt_s=interval,position_m=plain(position),
                            orientation=plain(pose[0][1]),velocity_generalized=plain(velocity),
                            active_contact_ids=plain(contacts),supported_bearing_ids=plain(bearing),dwell=plain(value)))
                        return value
                namespace['trap_event_v2']=SimpleNamespace(**{**vars(original_trap),'TrapMonitor':ObservedMonitor})
                # Count only actual original outer force invocations, without
                # replacing their return or any equation/health predicate.
                original_force=native.inertial_contact_step;count=[0]
                def counted(*args,**kwargs):
                    runtime._dispatch();need(count[0]<rows,'original smoke32 all-work cap');count[0]+=1
                    return original_force(*args,**kwargs)
                class InertialProxy:
                    inertial_contact_step=staticmethod(counted)
                    def __getattr__(self,key):return getattr(native,key)
                namespace['inertial']=InertialProxy()
                reference=FunctionType(candidate.__code__,namespace,candidate.__name__,candidate.__defaults__,candidate.__closure__)
                reference.__kwdefaults__=copy.copy(candidate.__kwdefaults__)
                with runtime.capture.scope('original_nominal',{}) as evidence:
                    args,kwargs=_smoke_arguments(runtime,pause=rows)
                    result=plain(reference(*args,**kwargs))
                need(result['status']=='paused_checkpoint' and len(observed)==rows and count[0]==rows,
                     'complete32 nominal reference without event/reject/hidden work')
                runtime.packet_work=count[0];cp=result['checkpoint'];source_proof={**proof,
                    'reference_original_full_integrator':True,'namespace_observers_return_exact_original_values':True,
                    'production_controller_checkpoint_emitted':False}
        need(runtime.packet_work==rows and result['rejected']==0 and cp['state']['pending_trial'] is None,
             'exact32 complete original physical substeps')
        if hasattr(runtime.capture,'inner_proofs'):
            source_proof['original_inner_scope_proofs']=plain(runtime.capture.inner_proofs)
        result['stage119_repair_calls']=plain(evidence['stage119_repair_calls'])
        result['history']=cp['state']['history']
        # Metadata declares the new source association. No one-extra-cap proof
        # is forged for the compiled administrative machine.
        record=dict(spec=plain(runtime.spec),result=result,rows=plain(observed),
            input_checkpoint_sha256=original_digest(None),effective_binding=runtime.provider['namespace']['binding_for'](runtime.binding,True),
            design_sha256=design_sha256,step_cap=rows,declared_total_step_ceiling=rows,
            minimum_gap_semantics=gap_semantics,numerical_policy_contract_sha256=numerical_contract_sha256,
            fresh_stack_policy_contract_not_old_raw_gap_acceptance=True,
            **{k:plain(v) for k,v in evidence.items() if k!='stage119_repair_calls'},
            smoke_source_proof=source_proof)
        if mode=='original':
            record['onset_timecap']=dict(enabled=True,policy=plain(selector.POLICY),journal=plain(journal),
                source_sha256=hashlib.sha256(Path(selector.__file__).read_bytes()).hexdigest(),source_ast_proof=proof)
        else:record['cap_entries']=plain(journal)
        return dict(record=record,work_rows=rows,mode=mode,source_proof=source_proof,
            physical_checkpoint=cp,discarded_diagnostic_only=True,core_result_admitted=False)
    finally:
        runtime.nominal_smoke_passthrough=False;native.set_recovery_mode(recovery)


def native_single_branch_smoke(spec,binding,dispatch_gate,*,mode,rows=32,plan_path,auth_path,physical_path,
                               limits,environment=None):
    """One registered original32 or compiled-C32 request; never warms implicitly."""
    grant=dispatch_gate()
    need(grant.get('native_dispatch_authorized') is True and grant.get('native_smoke_authorized') is True,
         'explicit standalone32 smoke diagnostic request')
    def run(env):
        physical=json.loads(Path(physical_path).read_text(encoding='utf-8-sig'))
        reconstruction=importlib.import_module('reconstruct_fixed_pose_v3')
        return _native_smoke(env['runtime'],limits,mode,hashlib.sha256(Path(physical_path).read_bytes()).hexdigest(),
            physical['minimum_gap_semantics'],hashlib.sha256(Path(reconstruction.s.q.job.WORK).read_bytes()).hexdigest(),rows=rows)
    if environment is not None:return run(environment)
    with native_execution_scope(spec,binding,dispatch_gate,plan_path=plan_path,auth_path=auth_path,
                                physical_path=physical_path,numerical=True) as env:return run(env)


def trace_rows(packet):
    return [[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']]
            for r in packet['accepted_rows']]


def packet_summary(packet):
    branches=packet['work_branches'];first=None;offset=0
    by_id={b['branch_id']:b for b in (*branches,*packet['carried_branches'])}
    for identity in packet['committed_branch_ids']:
        b=by_id[identity]
        if first is None and any(x['trigger_grain_ids'] for x in b['cap_entries'][:len(b['rows'])]):first=offset
        offset+=len(b['rows'])
    coarse=sum(b['work_rows'] for b in branches if b['role']=='C')
    new_by_id={b['branch_id']:b for b in branches}
    rejected=sum(sum(new_by_id[i]['work_rows'] for i in t['branch_ids'] if i in new_by_id)
        for t in packet['trials'] if t['decision']['action']=='discard_all_and_halve')
    return dict(work_rows=packet['work_rows'],accepted_rows_count=len(packet['accepted_rows']),
        coarse_shadow_rows=coarse,rejected_rows=rejected,
        known_unaccepted_rows=packet['work_rows'] if packet['status']=='negative' else
            sum(b['work_rows'] for b in branches if b['error'] is not None),unknown_rows=0,
        status=packet['status'],time_s=packet['checkpoint']['physical_checkpoint']['state']['t'],
        first_accepted_trigger_index_or_None=first,
        original_pending_trial=packet['checkpoint']['physical_checkpoint']['state']['pending_trial'],
        controller_pending_phase=packet['cursor_after']['phase'])


def numeric_restart_signature(packet):
    cp=packet['checkpoint']
    pending_keys=('branch_id','role','input_state_token','output_state_token','rows','cap_entries',
                  'history_delta','requested_dt_s','target_time_s','work_rows','result_status','error')
    return dict(physical_checkpoint=cp['physical_checkpoint'],published_state_token=cp['published_state_token'],
        cursor=cp['cursor'],numeric_ledger=cp['numeric_ledger'],history_root=cp['history_root'],
        staged_frames=cp['frames'],
        pending_branches=[{k:b.get(k) for k in pending_keys} for b in cp['pending_branches']])


READINESS=dict(actual_original_loop_compiler=True,source_only_controls_passed=True,
    actual_original_native_scope_bridge_implemented=True,explicit_nonadvancing_prelude_counted_separately=True,
    single_original_branch_smoke_bridge_implemented=True,compact_structural_history_implemented=True,
    original_substep_capture_native_qualified=False,mechanical_stencil_composition_qualified=False,
    full_controller_restart_native_qualified=False,terminal_export_qualified=False,
    execution_authority=False,numerical_launch_ready=False)


if __name__=='__main__':
    raise SystemExit('Inactive import/compile adapter only. No numerical launcher or authority command exists.')
