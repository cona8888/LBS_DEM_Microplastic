"""Independent exact trajectory and byte-storage qualification audit."""
from pathlib import Path
import qualify_immutable_field_v1 as u
api,parent=u.api,u.parent
OUT=u.OUT.parent/'independent_audit_01'


def main():
    d=api.read(u.DESIGN);u.verify(d);r=api.read(u.OUT/'results.json');s=api.read(u.OUT/'completion.json')
    api.require(not (u.OUT/'failure.json').exists() and s['results_sha256']==api.sha(u.OUT/'results.json'),'terminal seal')
    api.verify_mapping(r['artifacts']);seen=set();count=0
    for case in d['cases']:
        original=parent.storage.read_record(Path(case['source']),case['source_design_sha256'])
        spec=original['spec'];binding=api.digest([d['binding'],case['id']]);before=parent.model.checkpoint(spec,binding,original['result']['checkpoint'],True)
        records=[]
        for variant in ['uncached','cached']:
            path=u.RUN/(case['id']+'_'+variant+'.json.gz');seen.add(str(path));rec=parent.storage.read_record(path,api.sha(u.DESIGN));res=rec['result'];cp=res['checkpoint']
            api.require(rec['input_checkpoint_sha256']==api.digest(before) and rec['spec']==spec,'input lineage')
            api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==parent.engine.prior.contracts.expected_contract(spec,parent.model.binding_for(binding,True)),'checkpoint binding')
            api.require(res['rejected']==before['state']['rejected']==0,'zero rejection')
            api.require(parent.engine.prior.reference.independent_health(res,spec)['passed'],'numerical health')
            time=before['state']['t']
            for row in rec['rows']:
                api.require(row['dt_s']>0 and time+row['dt_s']==row['time_s'],'exact clock');time=row['time_s']
            api.require(time==res['time_s'] and len(rec['rows'])==case['steps']==res['steps']-before['state']['steps'],'step accounting')
            count+=len(rec['rows']);records.append(rec)
        api.require(records[0]['rows']==records[1]['rows'] and records[0]['result']['checkpoint']['state']==records[1]['result']['checkpoint']['state'],'exact cached versus uncached states')
    api.require(seen=={str(x) for x in u.RUN.glob('*.json.gz')}=={x for x in r['artifacts'] if x.endswith('.json.gz')},'inventory')
    api.require(count==r['new_steps']==d['maximum_new_steps'] and r['wall_s']<=d['maximum_wall_s'],'work bounds')
    api.require(all(x['passed'] for x in r['guards']) and r['full_exit_hashes_passed'],'guard verdicts')
    # Independent tiny-array ownership and alias checks exercise the mechanism.
    a,_=u.snapshot.freeze(u.np.arange(30.).reshape(3,2,5))
    for view in [a,a.view(),a.reshape(-1),a.T]:
        api.require(isinstance(u.snapshot.owner(view),bytes) and not view.flags.writeable,'immutable owner chain')
        try:view.setflags(write=True)
        except ValueError:pass
        else:raise RuntimeError('writable immutable alias')
    report={'passed':True,'new_steps_audited':count,'raw_records':len(seen),'exact_all_rows_and_checkpoint_states':True,
            'immutable_alias_guards_passed':True,'source_sha256':api.sha(__file__),'design_sha256':api.sha(u.DESIGN),
            'results_sha256':api.sha(u.OUT/'results.json'),'campaign_launched':False,'full_path_qualified':False}
    OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('SNAPSHOT_AUDIT',True,'STEPS',count,flush=True)


if __name__=='__main__':main()
