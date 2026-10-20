"""Separate saved-record audit; no integration or alterations to old evidence."""
from pathlib import Path
import copy
import qualify_budget_continuation_v1 as q
job,api=q.job,q.api
OUT=q.OUT.parent/'independent_continuation_01'

def main():
    p=api.read(q.DESIGN);q.verify(p);d=api.read(job.DESIGN)
    r=api.read(q.OUT/'results.json');api.require(r['passed'] and api.read(q.OUT/'completion.json')['results_sha256']==api.sha(q.OUT/'results.json'),'sealed producer qualification')
    api.verify_mapping(r['artifacts']);case=next(c for c in d['cases'] if c['id']==d['stress_case'])
    seed=api.read(q.RUN/'selected_seed.json')['checkpoint'];fine_seed=api.read(q.RUN/'conditional_fine_seed.json')['checkpoint']
    old,_=job.codec.read_record(q.OLD,api.sha(job.DESIGN));compiled,_=job.codec.read_record(q.COMPILED,api.sha(q.COMPILED_DESIGN))
    api.require(seed==old['result']['checkpoint'],'exact source seed')
    cp={};states={};records={};summaries=[];total=0
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        geo=q.pre.prior.geometry()
        for label in p['calls']:
            c=case;prefix=None;before=seed
            if label=='split_b':before=cp['split_a'];prefix=states['split_a']
            if label=='selected_tail':before=cp['selected_long'];prefix=states['selected_long']
            if label=='conditional_fine':c=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125');before=fine_seed
            path=q.RUN/(label+'.json.xz');launch=api.read(path.with_suffix('.launch.json'));account=api.read(path.with_suffix('.accounting.json'))
            api.require(launch['input_checkpoint_sha256']==api.digest(before) and launch['reserved_steps']==p['calls'][label],'ancestry and reservation')
            raw,state=job.codec.read_record(path,api.sha(job.DESIGN),prefix)
            check=job.kernel.evaluate(raw,c['spec'],job.binding(d,c),before,geo,api.sha(job.DESIGN),d['minimum_gap_semantics'])
            n=len(raw['rows']);api.require(0<n<=p['calls'][label] and account['accepted_steps']==n and account['raw_sha256']==api.sha(path),'exact accepted count and seals')
            api.require(check['passed'] and raw['result']['rejected']==before['state']['rejected'],'original numerical and rejection gate')
            total+=n;cp[label]=raw['result']['checkpoint'];states[label]=state;records[label]=raw
            summaries.append({'label':label,'steps':n,'audit':check,'raw_sha256':api.sha(path)})
    api.require(records['serial']['rows']==compiled['rows'][4915:5185] and cp['serial']['state']==compiled['result']['checkpoint']['state'],'exact separate implementation overlap')
    api.require(records['split_a']['rows']+records['split_b']['rows']==records['serial']['rows'] and cp['split_b']==cp['serial'],'exact restart')
    api.require(records['selected_long']['rows'][:270]==records['serial']['rows'],'long restart overlap')
    api.require(total==r['new_accepted_steps'] and total<=p['maximum_new_steps'] and 35426+total<=100000,'resolved bounded ledger')
    result={'passed':True,'new_accepted_steps':total,'cumulative_recovery_steps':35426+total,'remaining_recovery_steps':100000-35426-total,'audits':summaries,'source_results_sha256':api.sha(q.OUT/'results.json'),'old_probe_contracts_remain_failed':True,'new_production_authorized':False,'scope':'Exact local continuation across observed incomplete_budget with null pending trial; not full observation or deadline forecast.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('INDEPENDENT_CONTINUATION_PASS',total,flush=True)

if __name__=='__main__':main()
