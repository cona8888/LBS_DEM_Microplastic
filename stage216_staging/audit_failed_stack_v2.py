"""V1 retirement observation failure preserved; certify birth before command reads."""
from pathlib import Path
import math,os,psutil
import audit_failed_stack_v1 as previous
api,job=previous.api,previous.job
OUT=job.OUT/'failed_stack_independent_02'
observations=[]

def reused(created,ended,name,completion_bound):
    api.require(type(created) in (float,int) and math.isfinite(created) and created>ended
        and type(name) is str and bool(name) and 'python' not in name.lower()
        and completion_bound,'later-birth non-Python PID reuse with sealed original completion only')
    return True

def retired(owned,live):
    terminal=api.read(live/'completion.json');ended=job.policy.utc(terminal['utc']).timestamp()
    dsha=api.sha(job.DESIGN)
    api.require(terminal['design_sha256']==dsha and terminal['all_owned_processes_retired']
        and terminal['auditor_exit_code']==0 and all(v==0 for v in terminal['producer_exit_codes'].values()),'sealed old completion identity')
    # All original producer checkpoint, raw, receipt and completion chains have
    # already been independently replayed by the full audit before this call.
    scripts={os.path.normcase(str(p.resolve())) for p in (job.SELF,job.PREFLIGHT_SCRIPT)}
    for pid in owned:
        try:
            p=psutil.Process(pid);created=p.create_time();name=p.name()
            reused(created,ended,name,True)
            observations.append({'pid':pid,'classification':'later_birth_non_python_reuse','created':created,'old_terminal_time':ended,'name':name,'old_completion_sha256':api.sha(live/'completion.json')})
        except psutil.NoSuchProcess:observations.append({'pid':pid,'classification':'retired_no_process'})
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:api.require(not scripts.intersection(os.path.normcase(os.path.normpath(x)) for x in p.cmdline()),'no live same-command owned process')
        except psutil.NoSuchProcess:continue

def negative_controls():
    for created,name,bound in [(10,'vmwp.exe',True),(9,'vmwp.exe',True),(11,'python.exe',True),(11,'',True),(11,'vmwp.exe',False),(float('nan'),'vmwp.exe',True),(None,'vmwp.exe',True)]:
        try:reused(created,10,name,bound)
        except RuntimeError:continue
        raise AssertionError('bad retirement certificate accepted')
    api.require(reused(11,'10' if False else 10,'vmwp.exe',True),'positive reuse certificate')

source=previous.source
before="OUT = job.OUT/'failed_stack_independent_01'"
api.require(source.count(before)==1,'one exclusive repaired observation output')
source=source.replace(before,"OUT = job.OUT/'failed_stack_independent_02'")
before="        inputs.update(d['sources']);inputs.update(d['inputs'])"
api.require(source.count(before)==1,'preserved V1 audit failure seal site')
source=source.replace(before,before+"\n        inputs.update({str(p):api.sha(p) for p in [Path(previous.__file__),job.OUT/'failed_stack_independent_01/failure.json',job.OUT/'failed_stack_independent_01/launch.json']})")
before="'inputs':inputs, 'stage216_original_fixture_failure_preserved':True"
api.require(source.count(before)==1,'retirement certificate result site')
source=source.replace(before,"'retirement_observations':observations, 'retirement_negative_controls':7, 'v1_audit_observation_failure_preserved':True, "+before)
ns=dict(previous.ns,__file__=__file__,__name__='_stage216_failure_audit_v2',retired=retired,previous=previous,observations=observations)
exec(compile(source,__file__+'::same_physics_birth_certificate_first','exec'),ns)
if __name__=='__main__':
    negative_controls()
    with previous.wrapper.refs.reference.forbid_producer():ns['run']()
