"""Retain the 18,200-step Stage192 protocol, exercise repaired-contact stress.

The archived protocol functions are reused with an isolated job namespace.
Only the serial/parallel seed and disclosed accounting labels change. There
is no numerical, process, exact-restart or 30-percent slowdown gate change.
"""
from pathlib import Path
from types import FunctionType
import inspect
import os
import shutil
import sys
import psutil
import repaired_stack_campaign_v1 as wrapper
job, api, q = wrapper.job, wrapper.api, wrapper.q
sys.path.insert(0, str(job.ROOT/'stage192_staging'))
import qualify_provenance_campaign_v1 as original
ROOT, RUN, OUT = job.ROOT, job.PREFLIGHT, job.OUT/'preflight_01'
SELF = Path(__file__).resolve()


def stress_seed(d):
    case = next(c for c in d['cases'] if c['id'] == d['stress_case'])
    record = q.independent_file(Path(d['stress_seed_raw']), api.sha(d['stress_seed_design']))
    before = record['result']['checkpoint']
    cp = job.parent.model.checkpoint(case['spec'], job.binding(d, case), before, True)
    api.require(cp['state'] == before['state'], 'stress diagnostic rebind changes contract only')
    return case, cp


namespace = {**vars(original), 'wrapper': wrapper, 'job': job, 'api': api, 'parent': job.parent,
             'ROOT': ROOT, 'RUN': RUN, 'OUT': OUT, 'SELF': SELF, 'stress_seed': stress_seed}
for name, fn in vars(original).items():
    if inspect.isfunction(fn) and fn.__module__ == original.__name__:
        namespace[name] = FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)

changes = {}
for name in ('run', 'probe'):
    source = inspect.getsource(getattr(original, name))
    old = "case = d['cases'][0]; cp, _ = seed(d, case)"
    api.require(source.count(old) == 1, 'one exact stress seed substitution in '+name)
    source = source.replace(old, 'case, cp = stress_seed(d)')
    if name == 'run':
        old = "'prior_local_repair_steps': 20000, 'work_qualification_steps': new_steps+20000"
        new = "'prior_stage190_local_repair_steps': 20000, 'prior_stage194_steps': 40589, 'work_qualification_steps': new_steps, 'stage194_plus_stage195_steps': new_steps+40589"
        api.require(source.count(old) == 1, 'one explicit result-ledger substitution')
        source = source.replace(old, new)
    exec(compile(source, str(SELF)+'::explicit_'+name, 'exec'), namespace)
    changes[name] = {'stress_seed_substitutions': 1, 'result_ledger_substitutions': int(name == 'run')}

original_call = namespace['call']


def call(d, case, cp, name, cap, geo, prefix=None):
    # Publish a bounded reservation before every probe, then preserve exact
    # accounting immediately on return even if a following comparison fails.
    path = RUN/'probes'/(name+'.json.xz'); path.parent.mkdir(exist_ok=True)
    job.commit(path.with_suffix('.launch.json'), {'case': case['id'], 'step_cap': cap,
        'input_checkpoint_sha256': api.digest(cp), 'pid': os.getpid(), 'design_sha256': api.sha(job.DESIGN)})
    record, state, receipt = original_call(d, case, cp, name, cap, geo, prefix)
    job.commit(path.with_suffix('.accounting.json'), {'accepted_steps':len(record['rows']), 'raw_sha256':api.sha(path), 'rejected':record['result']['rejected']})
    if name == 'serial':
        oracle = q.independent_file(Path(d['stress_oracle_raw']), api.sha(d['stress_oracle_design']))
        api.require(record['rows'] == oracle['rows'][:cap], 'exact independently qualified repaired-contact oracle prefix')
    return record, state, receipt


namespace['call'] = call
seed, geometry, probe, protocol_fixtures = [namespace[k] for k in ('seed', 'geometry', 'probe', 'protocol_fixtures')]
_run = namespace['run']


def run():
    d = api.read(job.DESIGN); job.verify(d)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['pid'] == os.getpid() or 'python' not in (proc.info['name'] or '').lower(): continue
        command = ' '.join(proc.info['cmdline'] or []).lower()
        api.require('matdem_microplastic' not in command, 'no competing workspace simulation or audit')
    api.require(shutil.disk_usage(ROOT).free > d['budget']['minimum_free_disk_bytes']+4*q.repair.base.MAX_COMPRESSED, 'preflight disk reserve')
    return _run()


if __name__ == '__main__':
    if sys.argv[1:] == ['run']: run()
    elif len(sys.argv) == 3 and sys.argv[1] == 'probe': probe(sys.argv[2])
    else: raise ValueError('run | probe TAG')
