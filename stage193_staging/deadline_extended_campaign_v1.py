"""Administrative deadline amendment of the Stage192-qualified stack.

No trajectory implementation is edited. The original lifecycle source is
loaded in a private namespace; the exact qualified execute code object is
bound to this namespace. Reused preflight is disclosed, never relabelled as
new trajectory evidence. Production must start fresh in one exclusive root.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import marshal
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage192_staging'))
import qualified_provenance_campaign_v1 as qualified

old = qualified.job
spec = importlib.util.spec_from_file_location('_stage193_frozen_lifecycle', qualified.instance.historical.__file__)
job = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = job
spec.loader.exec_module(job)
api = job.api
job.SELF = Path(__file__).resolve()
job.BASE = 'deadline_extended_paired_campaign_20260924'
job.DESIGN = ROOT / 'stage193_designs' / job.BASE / 'design_01.json'
job.RUN = ROOT / 'stage193_runs' / job.BASE / 'run_01'
job.PREFLIGHT = ROOT / 'stage193_runs' / job.BASE / 'not_authorized'
job.OUT = ROOT / 'stage193_evaluations' / job.BASE
job.WORK = ROOT / 'stage193_designs/deadline_extension_20260924/authorization_01.json'
job.PREFLIGHT_SCRIPT = old.PREFLIGHT_SCRIPT
job.kernel, job.codec = old.kernel, old.codec
job.observer = qualified.instance.observer
job.execute_segment = types.FunctionType(old.execute_segment.__code__, dict(job.__dict__), 'execute_segment', old.execute_segment.__defaults__, old.execute_segment.__closure__)
BASE_DESIGN_SHA = '071703a7d298c03bb8b6f79563f862c63dab7443670ede701e92b493624b101b'
AUDIT = old.OUT / 'independent_readiness_01/results.json'
AUDIT_SHA = '94df3b72ae4693f761a99f9096cffef41bed5ec7dcee4c2d2f11fedde4f7a220'
BRIDGE = job.OUT / 'qualification_inheritance_01'
ALLOWED = {'stage','sources','inputs','binding','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc','guard','qualification_inheritance'}
IDENTICAL_FUNCTIONS = ('execute_segment','worker','auditor','audit_one','evaluate','stopping','acknowledged','binding','commit','root_settings','start_child','paths')
_supervise = job.supervise


def code_sha(fn):
    return hashlib.sha256(marshal.dumps(fn.__code__)).hexdigest()


def equivalence(d):
    original = api.read(old.DESIGN)
    api.require(api.sha(old.DESIGN) == BASE_DESIGN_SHA, 'qualified design SHA')
    changed = {k for k in set(d) | set(original) if d.get(k) != original.get(k)}
    api.require(changed <= ALLOWED, 'only explicitly administrative fields may change')
    work = api.read(job.WORK)
    api.require(d['simulation_cutoff_utc'] == work['simulation_cutoff_utc'] == '2026-09-26T18:59:00+00:00', 'approved simulation cutoff')
    api.require(d['final_audit_deadline_utc'] == d['agent_work_end_utc'] == work['final_audit_deadline_utc'] == '2026-09-26T22:59:00+00:00', 'approved final audit boundary')
    api.require(d['qualification_inheritance'] == {'design_sha256':BASE_DESIGN_SHA,'preflight_result_sha256':'7e24b5164826120d42a690f50bf756a331a3050e3e0e2f4eb7d822e8aa928dfd','independent_audit_sha256':AUDIT_SHA,'new_qualification_trajectory_steps':0}, 'exact disclosed qualification inheritance')
    api.require(all(d['sources'].get(p)==h for p,h in original['sources'].items()), 'every original frozen source remains bound')
    api.require(all(d['inputs'].get(p)==h for p,h in original['inputs'].items()), 'every original frozen input remains bound')
    api.require(d['sources'].get(str(job.SELF)) == api.sha(job.SELF) and d['inputs'].get(str(job.WORK)) == api.sha(job.WORK), 'new administrative code and authority bound')
    proofs = {}
    for name in IDENTICAL_FUNCTIONS:
        a, b = getattr(job,name), getattr(old,name)
        api.require(code_sha(a) == code_sha(b), 'identical qualified function '+name)
        proofs[name] = code_sha(a)
    api.require(job.kernel is old.kernel and job.codec is old.codec and job.observer is qualified.instance.observer, 'identical numerical auditor, codec and observer objects')
    g = job.execute_segment.__globals__
    for name in ('DESIGN','codec','kernel','observer','parent','fast','prior','deadline','capture'):
        api.require(g[name] == getattr(job,name), 'execute global routing '+name)
    api.require(g['binding'] is job.binding and g['commit'] is job.commit and job.worker.__globals__ is job.__dict__, 'new immutable run routing')
    return changed, proofs


def verify(d):
    old.verify(d)
    equivalence(d)


def inherited_preflight():
    d = api.read(old.DESIGN); old.verify(d)
    r = old.verify_preflight(d)
    api.require(api.sha(AUDIT) == AUDIT_SHA and api.read(AUDIT.parent/'completion.json')['results_sha256']==AUDIT_SHA, 'independent readiness audit seal')
    a = api.read(AUDIT)
    api.require(a['numerical_qualification_passed'] and a['readiness_audit_passed'] and a['raw_records_independently_decoded']==38 and len(a['numerical_reaudits'])==30, 'complete independent numerical qualification')
    api.require(r['new_steps']==18200 and r['work_qualification_steps']==38200, 'unexpanded step ledger')
    return r


def verify_preflight(d):
    verify(d); r = inherited_preflight()
    p = api.read(BRIDGE/'results.json')
    api.require(api.read(BRIDGE/'completion.json')['results_sha256']==api.sha(BRIDGE/'results.json'), 'inheritance seal')
    api.require(p['passed'] and p['design_sha256']==api.sha(job.DESIGN) and p['new_trajectory_steps']==0 and p['source_sha256']==api.sha(job.SELF), 'inherited qualification bound to this design')
    api.require(p['function_identity_sha256']==equivalence(d)[1], 'qualified function identities unchanged')
    return r


job.verify, job.verify_preflight = verify, verify_preflight


def resource_gate(d):
    r = verify_preflight(d)
    required=max(d['resource_scenario']['hours_with_margin'],d['provenance_transaction_hours_with_margin'],r['refreshed_hours_with_margin'])
    available=(job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    free=job.shutil.disk_usage(ROOT).free
    need=d['provenance_bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
    api.require(available >= required, 'original conservative runtime margin fits approved deadline')
    api.require(free >= need, 'full provenance storage and original reserve')
    return {'required_hours':required,'available_hours':available,'required_storage_with_reserve_bytes':need,'free_disk_bytes':free}


def supervise(mode):
    api.require(mode=='campaign','no new qualification trajectories authorized by deadline amendment')
    resource_gate(api.read(job.DESIGN))
    return _supervise(mode)


job.supervise = supervise


def prepare():
    d=copy.deepcopy(api.read(old.DESIGN)); inherited_preflight()
    api.require(not job.RUN.exists(), 'fresh exclusive campaign only')
    work=api.read(job.WORK)
    d.update(stage='Stage193 deadline-amended original six-case campaign',
             simulation_cutoff_utc=work['simulation_cutoff_utc'],final_audit_deadline_utc=work['final_audit_deadline_utc'],agent_work_end_utc=work['final_audit_deadline_utc'],
             guard='Unchanged qualified Stage192 runtime; exact frozen scientific-design and function equivalence, hash-bound inherited preflight, and refreshed original resource gates required before one fresh launch.',
             qualification_inheritance={'design_sha256':BASE_DESIGN_SHA,'preflight_result_sha256':api.sha(old.OUT/'preflight_01/results.json'),'independent_audit_sha256':AUDIT_SHA,'new_qualification_trajectory_steps':0})
    d['sources'][str(job.SELF)]=api.sha(job.SELF)
    for p in (job.WORK,old.DESIGN,AUDIT,AUDIT.parent/'completion.json',old.OUT/'preflight_01/results.json',old.OUT/'preflight_01/completion.json'):
        d['inputs'][str(p)]=api.sha(p)
    d['binding']=api.digest({k:v for k,v in d.items() if k!='binding'})
    job.DESIGN.parent.mkdir(parents=True,exist_ok=False); api.write(job.DESIGN,d)
    verify(d)
    changed, proofs=equivalence(d)
    rejects=[]
    mutations=[('time_step',lambda x:x['cases'][0].update(factor=1)),
               ('case_removal',lambda x:x['cases'].pop()),
               ('budget',lambda x:x['budget'].update(max_new_steps_total=999999999)),
               ('gates',lambda x:x['numerical_gates'].update(wrong=1)),
               ('geometry_semantics',lambda x:x.update(minimum_gap_semantics='wrong')),
               ('codec',lambda x:x.update(codec_schema='wrong')),
               ('unapproved_cutoff',lambda x:x.update(simulation_cutoff_utc='2026-09-27T18:59:00+00:00')),
               ('wrong_qualification',lambda x:x['qualification_inheritance'].update(new_qualification_trajectory_steps=1)),
               ('source_omission',lambda x:x['sources'].pop(next(iter(api.read(old.DESIGN)['sources']))))]
    for name,mutate in mutations:
        bad=copy.deepcopy(d);mutate(bad)
        try:equivalence(bad)
        except (AssertionError,ValueError,RuntimeError):rejects.append(name)
        else:raise AssertionError('administrative bridge accepted '+name)
    BRIDGE.mkdir(parents=True,exist_ok=False)
    result={'passed':True,'design_sha256':api.sha(job.DESIGN),'source_sha256':api.sha(job.SELF),'changed_fields':sorted(changed),
            'function_identity_sha256':proofs,'corrupt_amendments_rejected':rejects,'new_trajectory_steps':0,
            'qualification_reused_not_rerun':True,'inherited_preflight_steps':18200,'separate_local_repair_steps':20000,
            'utc':job.utc().isoformat(),'claim':'Administrative equivalence and inherited qualification only. No new trajectory, full observation or release result.'}
    job.commit(BRIDGE/'results.json',result);job.commit(BRIDGE/'completion.json',{'passed':True,'results_sha256':api.sha(BRIDGE/'results.json')})
    print('AMENDMENT_READY',api.sha(job.DESIGN),json.dumps(resource_gate(d)),flush=True)


if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif args==['check']:print(json.dumps(resource_gate(api.read(job.DESIGN))),flush=True)
    elif args==['supervise','campaign']:job.supervise('campaign')
    elif len(args)==3 and args[:2]==['worker','campaign']:job.worker('campaign',args[2])
    elif args==['auditor','campaign']:job.auditor('campaign')
    elif args==['evaluate','campaign']:job.evaluate('campaign')
    else:raise ValueError('prepare | check | supervise campaign | worker campaign CASE | auditor campaign | evaluate campaign')
