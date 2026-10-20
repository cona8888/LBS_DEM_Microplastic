"""Post-exit three-level onset audit; never grants full Paper1 case admission."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
import paper1_onset_window_v1 as run
s=run.s


def controls():
    initial=[.373,0.,0.,0.,1.,0.,0.,0.,0.,0.,0.,0.,0.]
    rows=np.asarray([[.383,0.,0.,0.,1.,0.,0.,0.,0.,0.,0.,0.,0.],
                     [.423,0.,0.,0.,1.,0.,0.,0.,0.,0.,0.,0.,0.]])
    metrics=s.q.job.path_metrics.metrics([rows],[rows],initial,initial,.423,.423,1.,1.)
    assert metrics['common_start_s']==.373 and metrics['common_stop_s']==.423
    assert metrics['mean_L1_q_over_U_max']==0. and metrics['endpoint_q_over_U_max']==0.
    observation=dict(complete_observation=False,status='local_diagnostic_only')
    verdict=s.q.job.policy.pair_gates(observation,observation,metrics,s.q.job.policy.GATES)
    assert not verdict['passed']
    try:
        s.q.job.policy.pair_gates(dict(complete_observation=True,stop_s=.423),
                                 dict(complete_observation=True,stop_s=.423),metrics,s.q.job.policy.GATES)
    except ValueError:
        pass
    else:
        raise AssertionError('A nonzero-start local path passed a full fresh-path gate')
    assert run.transaction.__code__ is run.original.transaction.__code__
    return dict(passed=True,new_transport_steps=0,absolute_clock_preserved=True,
                identical_local_trace_error_zero=True,local_observation_cannot_pass_original_full_path_gate=True,
                forged_complete_flag_does_not_bypass_original_fresh_clock=True,
                original_transaction_bytecode_unchanged=True)


def evaluate(observed_exit,session):
    controls();root=run.OUT;p=run.read(run.PLAN);d=run.read(run.PHYSICAL)
    s.require(run.datetime.now(run.timezone.utc)<run.datetime.fromisoformat(p['end_utc']), 'Absolute onset audit cutoff')
    readiness=s.fields.sealed(run.DESIGNS/'readiness_01/results.json')
    s.require(readiness['passed'],'Qualified local diagnostic audit preparation')
    s.api.verify_mapping(readiness['source_files'])
    s.require(observed_exit==0,'Actual successful local supervisor exit')
    final=s.fields.sealed(root/'final_disposition_01/results.json')
    s.require(final['passed'] and final['diagnostic_only'] and final['native_complete']
        and not final['original_paper1_horizon_complete'] and not final['core_result_admitted']
        and final['known_unaccepted_saved_steps']==final['unknown_reserved_steps_upper_bound']==0,'Complete local diagnostic only')
    s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['physical_inputs'])
    identities=[]
    for path in (root/'controller_01/launch.json',root/'controller_01/worker_launch.json',root/'worker_launch.json'):
        identity=run.read(path);state=s.identity(identity);s.require(state['retired'],'Exact local identities retired')
        identities.append(dict(path=str(path),sha256=s.sha(path),inspection=state))
    exit=run.read(root/'controller_01/exit.json');s.require(exit['returncode']==0,'Actual local worker exit');s.api.verify_mapping(exit['logs'])
    codec=run.original.archives.build(s.q.job.codec,preset=9)
    traces=[];ends=[];accounted=0;artifacts={}
    for i,case in enumerate(d['cases']):
        seed,_=run.seed_for(i)
        def read_record(label,prefix,before):
            folder=root/'records'/label;gate=s.fields.sealed(folder/'guard_completion/results.json')
            s.api.verify_mapping(gate['artifacts']);audit=run.DOC.read(folder/'results.json')
            s.require(gate['passed'] and audit['passed'] and audit['summary']['passed'],'Unchanged per-record independent physical audits')
            rec,newprefix=codec.read_record(folder/'call.json.xz',run.sha(run.PHYSICAL),prefix)
            cp=rec['result']['checkpoint']
            s.require(rec['spec']==case['spec'] and rec['input_checkpoint_sha256']==s.api.digest(before)
                and gate['full_checkpoint_sha256']==s.api.digest(cp),'Exact complete raw ancestry')
            s.require(cp['state']['steps']-before['state']['steps']==len(rec['rows'])
                and audit['summary']['start_s']==before['state']['t'] and audit['summary']['stop_s']==cp['state']['t'],'All absolute clock/step increments')
            expected=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],float)
            path=folder/'trace.npy';s.require(np.array_equal(np.load(path,allow_pickle=False),expected),'Trace losslessly reconstructed from every raw row')
            artifacts.update(gate['artifacts']);artifacts[str(folder/'guard_completion/results.json')]=run.sha(folder/'guard_completion/results.json')
            return rec,newprefix,path
        a,_,_=read_record(f'branch{i}_serial',None,seed)
        b,bp,_=read_record(f'branch{i}_split_a',None,seed)
        c,_,_=read_record(f'branch{i}_split_b',bp,b['result']['checkpoint'])
        s.require(len(a['rows'])==256 and len(b['rows'])==len(c['rows'])==128
            and s.api.digest(a['rows'])==s.api.digest(b['rows']+c['rows'])
            and s.api.digest(a['result']['checkpoint'])==s.api.digest(c['result']['checkpoint']),'Exact late-seed restart independently reconstructed')
        accounted+=512;before=seed;prefix=None;paths=[]
        for label in final['branches'][i]['labels']:
            rec,prefix,path=read_record(label,prefix,before);accounted+=len(rec['rows']);before=rec['result']['checkpoint'];paths.append(path)
        s.require(before['state']['t']==case['spec']['horizon_s'] and s.api.digest(before)==final['branches'][i]['checkpoint_sha256'],'Complete declared local interval')
        s.require(s.api.digest(run.DOC.read(root/f'recoverable_{i}/checkpoint.json'))==s.api.digest(before),'Standalone complete local checkpoint')
        traces.append(paths);ends.append(before['state']['t'])
    s.require(accounted==final['discarded_diagnostic_steps'] and accounted<=71536,'All new work remains discarded diagnostic work')
    listed=[run.read(x)['label'] for x in sorted((root/'reservations').glob('*.json'))]
    s.require(set(listed)==set(final['production_labels']) and len(listed)==len(set(listed)) and len(listed)<=26,'No omitted reservation or failed call')
    seed,_=run.seed_for(0);state=seed['state'];initial=[state['t'],*state['x'],*state['p'],*state['q']]
    def blocks(paths):
        for path in paths:yield np.load(path,mmap_mode='r',allow_pickle=False)
    spec=d['cases'][0]['spec']
    s.require(len(traces)==len(ends)==len(d['cases'])==3,'Three prospectively fixed numerical levels')
    metrics=[]
    for i in (0,1):
        pair=s.q.job.path_metrics.metrics(blocks(traces[i]),blocks(traces[i+1]),initial,initial,ends[i],ends[i+1],
            spec['config']['prolate_semiaxes_m'][1],spec['config']['target_mean_interstitial_velocity_m_s'])
        metrics.append(dict(factors=[d['cases'][i]['factor'],d['cases'][i+1]['factor']],metrics=pair))
    run.seal(root/'evaluation_01',dict(passed=True,diagnostic_evidence_only=True,local_metrics=metrics,
        observed_supervisor_exit_code=observed_exit,root_exec_session_id=session,all_exact_owned_identities_retired=True,
        source_files={str(Path(__file__).resolve()):run.sha(Path(__file__)),**p['source_files']},
        artifacts=artifacts,closed_logs=exit['logs'],identities=identities,
        discarded_diagnostic_steps=accounted,conservative_call_charges=len(listed),
        original_full_path_admission=False,publication_case_count_increment=0,utc=s.utc()))
    print('ONSET_DIAGNOSTIC_AUDITED',run.sha(root/'evaluation_01/results.json'),metrics,flush=True)


if __name__=='__main__':
    if sys.argv[1]=='controls':print(controls())
    else:evaluate(int(sys.argv[1]),int(sys.argv[2]))
