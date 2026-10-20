"""Fresh campaign instance combining qualified provenance and lossless storage.

The 20,000-step local regression belongs to the repair work ledger, not this
fresh campaign. This campaign retains the original 18,200-step preflight and
80,020,000 inclusive production/preflight ceiling. Both ledgers are disclosed.
"""
from pathlib import Path
import copy
import importlib.util
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage190_staging'),str(ROOT/'stage191_staging')]
import audited_trial_campaign_v1 as historical_wrapper
import qualify_trial_references_v1 as storage_qualification
import lossless_trial_references_v1 as compact

spec=importlib.util.spec_from_file_location('_stage192_isolated_stage190',historical_wrapper.__file__)
instance=importlib.util.module_from_spec(spec);sys.modules[spec.name]=instance;spec.loader.exec_module(instance)
job=instance.job;api=job.api
job.SELF=Path(__file__).resolve();job.BASE='qualified_provenance_campaign_20260924'
job.DESIGN=ROOT/'stage192_designs'/job.BASE/'design_01.json'
job.RUN=ROOT/'stage192_runs'/job.BASE/'run_01'
job.PREFLIGHT=ROOT/'stage192_runs'/job.BASE/'preflight_01'
job.OUT=ROOT/'stage192_evaluations'/job.BASE
job.PREFLIGHT_SCRIPT=job.SELF.with_name('qualify_provenance_campaign_v1.py')
job.codec=compact.codec
job.execute_segment,_=instance.build_execute()
_verify=job.verify
_supervise=job.supervise


def verify(d):
    _verify(d)
    storage_qualification.verify(api.read(storage_qualification.DESIGN))
    api.require(d['codec_schema']==compact.SCHEMA and d['prior_local_repair_steps']==20000,'qualified storage and separate step ledger')


job.verify=verify


def supervise(mode):
    if mode=='campaign':
        d=api.read(job.DESIGN);verify(d);p=job.verify_preflight(d)
        required=max(d['resource_scenario']['hours_with_margin'],d['provenance_transaction_hours_with_margin'],p['refreshed_hours_with_margin'])
        api.require((job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600>=required,'all repaired-stack runtime costs fit deadline')
        api.require(job.shutil.disk_usage(ROOT).free-d['budget']['minimum_free_disk_bytes']>=d['provenance_bytes_with_margin'],'complete provenance storage and reserve')
    return _supervise(mode)


job.supervise=supervise


def prepare():
    q=storage_qualification;q.verify(api.read(q.DESIGN));r=api.read(q.OUT/'results.json')
    api.require(r['passed'] and r['new_trajectory_steps']==0,'lossless storage qualification')
    api.require(api.read(q.OUT/'completion.json')['results_sha256']==api.sha(q.OUT/'results.json'),'storage qualification seal')
    api.verify_mapping(r['artifacts'])
    original=instance.historical;d=copy.deepcopy(api.read(original.DESIGN));original.verify(d);d.pop('binding')
    work=api.read(job.WORK);api.require(job.utc()<job.policy.utc(work['agent_work_end_utc']),'authorized preparation')
    local=api.read(q.prior.OUT/'results.json');saved=api.read(api.read(q.prior.job.DESIGN)['diagnostic_seed'])
    old_ready=original.paths(original.RUN,saved['case'],138)['ready'];old_tx=api.read(old_ready)['transaction_seconds']
    measured=next(x for x in r['reports'] if x['name']=='serial')
    factor=max(1.,(local['cases'][0]['compute_s']+measured['write_s'])/old_tx)
    raw=Path(saved['oracle_path']);storage_factor=max(1.,measured['new_archive_bytes']/raw.stat().st_size)
    inputs=[original.DESIGN,job.WORK,q.DESIGN,q.OUT/'results.json',q.OUT/'completion.json',q.prior.DESIGN,q.prior.OUT/'results.json',old_ready,raw]
    d.update(stage='Stage192 qualified explicit-provenance fresh paired campaign',
        sources=job.source_map(),inputs={str(p):api.sha(p) for p in inputs},
        agent_work_end_utc=work['agent_work_end_utc'],simulation_cutoff_utc=work['simulation_cutoff_utc'],final_audit_deadline_utc=work['final_audit_deadline_utc'],
        audit_source_sha256=api.sha(job.kernel.__file__),observer_structure=instance.observer.STRUCTURAL_IDENTITY,
        audit_structure=job.kernel.STRUCTURAL_IDENTITY,execute_structure=instance.EXECUTE_IDENTITY,
        codec_schema=compact.SCHEMA,prior_local_repair_steps=20000,maximum_work_qualification_steps=60000,
        provenance_transaction_hours_with_margin=d['resource_scenario']['hours_with_margin']*factor,
        provenance_bytes_with_margin=d['resource_scenario']['bytes_with_margin']*storage_factor,
        measured_transaction_overhead_factor=factor,measured_storage_overhead_factor=storage_factor,
        claim='Original six fresh labelled observations only after all numerical, lifecycle and resource gates. Failed historical campaigns remain failed; no population release or empirical validation.')
    d['binding']=api.digest(d);job.DESIGN.parent.mkdir(parents=True,exist_ok=False);api.write(job.DESIGN,d);verify(d)
    print('FROZEN_CAMPAIGN',api.sha(job.DESIGN),'conservative_hours',d['provenance_transaction_hours_with_margin'],'bytes',d['provenance_bytes_with_margin'],flush=True)


if __name__=='__main__':
    a=sys.argv[1:]
    if a==['prepare']:prepare()
    elif len(a)==2 and a[0]=='supervise':job.supervise(a[1])
    elif len(a)==3 and a[0]=='worker':job.worker(a[1],a[2])
    elif len(a)==2 and a[0]=='auditor':job.auditor(a[1])
    elif len(a)==2 and a[0]=='evaluate':job.evaluate(a[1])
    else:raise ValueError('prepare | supervise MODE | worker MODE CASE | auditor MODE | evaluate MODE')
