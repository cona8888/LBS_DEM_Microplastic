"""Fresh record/kernel replay, exact serial/split identity and inclusive ledger."""
from pathlib import Path
import os,sys,psutil
import bounded_feasibility_diagnostic_v1 as base

def run(label,final=False):
    w,d=base.prerequisites(); api,job=base.api,base.job
    inputs={str(p):api.sha(p) for p in (Path(__file__),base.WORK,base.DESIGNBASE/'exact_endpoint_amendment_01.json')}
    records={};checks=[];saved=0
    case=next(c for c in d['cases'] if c['id']==w['case']); geom=base.geometry(case)
    names=['serial_01','split_a_01','split_b_01']
    if final:names+=['extension_a_01','extension_b_01','extension_c_01','extension_d_01']
    for name in names:
        out=base.RUNBASE/name; result=base.sealed(out/'results.json');plan=api.read(base.DESIGNBASE/(name+'.json'))
        api.verify_mapping(plan['inputs']);api.verify_mapping(plan['new_sources']);api.verify_mapping(result['artifacts'])
        seed=base.RUNBASE/plan['seed'] if plan['seed'] else base.RECON
        before=api.read(seed/('checkpoint.json' if plan['seed'] else 'checkpoint_00227.json'))
        prior=base.prefix(seed/('prefix.json' if plan['seed'] else 'prefix_00227.json'),seed/('history.json' if plan['seed'] else 'history_00227.json'))
        rec,state=base.frozen.pre.storage.codec.read_record(out/'call.json.xz',api.sha(job.DESIGN),prior)
        audit=base.auditor.kernel(rec,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        account=api.read(out/'accounting.json');steps=rec['result']['steps']-before['state']['steps']
        api.require(audit['passed'] and result['numerical_audit_passed'] and rec['result']['rejected']==0,'original numerical and zero-rejection gates '+name)
        api.require(0<steps==account['saved_steps']==result['steps']<=plan['maximum_new_steps'],'exact saved-step accounting '+name)
        api.require(account['launch_sha256']==api.sha(out/'launch.json') and state.reference()==api.read(out/'prefix.json'),'launch/history binding '+name)
        api.require(api.digest(rec['result']['checkpoint'])==api.digest(api.read(out/'checkpoint.json')),'full checkpoint binding '+name)
        records[name]=rec;saved+=steps
        checks.append(dict(name=name,steps=steps,passed=True,audit_seconds=audit['audit_seconds'],stop_s=rec['result']['time_s'],status=rec['result']['status']))
        for p in list(out.glob('*'))+[base.DESIGNBASE/(name+'.json')]:
            if p.is_file():inputs[str(p)]=api.sha(p)
    serial=records['serial_01']; a=records['split_a_01']; b=records['split_b_01']
    same_rows=serial['rows']==a['rows']+b['rows']
    same_cp=api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint'])
    api.require(same_rows and same_cp,'exact full-state/full-row serial versus split restart')
    used,pending=base.ledger();api.require(not pending and used==saved<=w['maximum_new_saved_trajectory_steps'],'all inclusive saved-step reservations closed')
    owned={str((Path(base.__file__).parent/x).resolve()) for x in ('bounded_feasibility_diagnostic_v1.py','bounded_feasibility_diagnostic_v2.py')}
    live=[]
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:
            argv=p.cmdline()
            if 'run' in argv and owned.intersection(argv):live.append(dict(pid=p.pid,argv=argv))
        except psutil.NoSuchProcess:continue
    api.require(not live,'all diagnostic identities retired')
    result=dict(passed=True,new_trajectory_steps=0,independently_passing_saved_steps=saved,unresolved_reservations=pending,exact_restart_full_rows=same_rows,exact_restart_full_checkpoint=same_cp,records=checks,all_owned_diagnostics_retired=True,inputs=inputs,claim='Bounded local qualification only; failed Stage205 stays failed. No production or full-path/release/validation claim.')
    out=base.EVALBASE/label
    job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')))
    print('INDEPENDENT_TRAJECTORY_AUDIT',label,saved,len(checks),api.sha(out/'results.json'),flush=True)

if __name__=='__main__':run(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='final')
