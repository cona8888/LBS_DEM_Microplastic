"""Frozen four-case CPU sensitivity test; reuse the Stage149 finest reference.

Three temporal levels are 4h, 2h, h, not an expensive automatic h/4 campaign.
Four independent single-thread processes maximum; no GPU or new physical model.
"""
from pathlib import Path
import copy
import gzip
import json
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage149_staging'))
import continue_selected_sphere_v1 as previous
api,parent,engine,hot=previous.api,previous.parent,previous.engine,previous.hot
method,audit,guard=previous.method,previous.audit,previous.guard
BASE='full_horizon_sphere_sensitivity_20260921'
DESIGN=ROOT/'stage150_designs'/BASE/'design_01.json'
RUN=ROOT/'stage150_runs'/BASE/'run_01'
OUT=ROOT/'stage150_evaluations'/BASE/'evaluation_01'


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])


def prepare():
    ev=api.read(previous.OUT/'results.json')
    api.require(ev['passed'] and api.read(previous.OUT/'completion.json')['results_sha256']==api.sha(previous.OUT/'results.json'),'Stage149 sealed completion')
    proto=api.read(previous.RUN/'protocol.json')
    api.verify_mapping(proto['sources']);api.verify_mapping(proto['inputs'])
    pd=api.read(parent.DESIGN);parent.verify(pd)
    c=next(c for c in pd['cases'] if c['id']=='sphere_12_terminal')
    inputs=[previous.OUT/'results.json',previous.OUT/'completion.json',previous.RUN/'protocol.json',parent.DESIGN,Path(c['source']),
            audit.OUT/'results.json',audit.OUT/'completion.json',audit.SOURCE/'local_factor_1_kappa_16.json']
    for item in ev['segments']:
        p=Path(item['path']);api.require(api.sha(p)==item['sha256'],'reference record')
        r=api.read(p);api.require(api.sha(p.parent/'intervals.json.gz')==r['intervals_sha256'],'reference intervals')
        inputs += [p,p.parent/'completion.json',p.parent/'intervals.json.gz']
    cases=[]
    for name,factor,kappa in [('dt4',4.,16),('dt2',2.,16),('kappa8',1.,8),('kappa64',1.,64)]:
        spec=copy.deepcopy(proto['spec'])
        for k in api.DT_CONTROLS:spec['config']['numerics'][k]*=factor
        cases.append({'id':name,'factor':factor,'kappa':kappa,'spec':spec,'source':c['source']})
    d={'stage':'Stage150','question':'Is the selected sphere continuation from the saved stationary-contact state to 0.1 PV insensitive to three timestep levels and three geometric arithmetic budgets?',
       'cases':cases,'reused_reference':str(previous.OUT/'results.json'),
       'time_levels_relative_to_reference':[4.,2.,1.],'geometric_multipliers':[8,16,64],
       'domain':'One selected seed-2 equal-volume sphere in fixed sand with frozen stationary CPD6 flow; inherited quasistatic rotation. Initial clock 0.7835207196064563 s, final 4.682166803491474 s. No inference about the earlier transport path.',
       'physical_changes':[],
       'limits':pd['limits'],
       'acceptance':'All four complete the same horizon, health and exact clocks pass, no fallback, same finite dwell/outlet verdict, event times within twice the largest accepted dt. Final AND whole-continuation common-clock position/b, axis and q/U differences obey inherited limits. Compare states using componentwise linear interpolation onto the union of recorded clocks; do not fit or shift clocks.',
       'budget':{'parallel_cpu_workers':4,'blas_threads_per_worker':1,'segment_wall_s':40,'max_segments_per_case':24,'case_wall_s':950,'segment_step_cap':30000},
       'pilot':'Each case first reaches the same existing Stage148 0.01 s local window and is compared under unchanged limits; no full dispatch if any pilot fails.',
       'stop':'Fail closed on physical/health/provenance failure, no useful progress, or budget exhaustion. Preserve failed cases.',
       'claim_boundary':'Continuation sensitivity for this one selected sphere only; not full-path convergence, population release, fibre qualification or experimental validation.',
       'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,previous.__file__,method.__file__,audit.__file__,guard.__file__]},
       'inputs':{str(p):api.sha(p) for p in inputs}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def execute(c,spec,cp,binding,steps):
    collector=previous.Certificates()
    with hot.scope(),parent.scope(spec),method.scope(spec,enabled=True,multiplier=c['kappa'],certificates=collector):
        r,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+steps)
    health=engine.prior.reference.independent_health(r,spec)
    clock=audit.clock_chain(cp['state']['t'],rows,r['time_s'])
    coordinates=all(max(np.abs(x['position_m']))<=spec['field_metadata']['cell_length_m'] for x in rows)
    passed=(health['passed'] and clock['passed'] and coordinates and collector.data['all_passed'] and not r.get('stage119_repair_calls')
            and r['checkpoint']['state_sha256']==api.digest(r['checkpoint']['state']) and len(rows)==r['steps']-cp['state']['steps'])
    return r,rows,{'passed':passed,'health':health,'clock':clock,'contact_certificates':collector.data,'coordinate_scale':coordinates}


def pilot(d):
    folder=RUN/'pilots';folder.mkdir(parents=True,exist_ok=False)
    parent.old.prior.prior.configure();hot.warmup()
    reference=api.read(audit.SOURCE/'local_factor_1_kappa_16.json')
    rows=[]
    for c in d['cases']:
        spec=copy.deepcopy(c['spec']);spec['horizon_s']=reference['result']['time_s'];spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
        cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint']);binding=api.digest([d['binding'],'pilot',c['id']])
        cp['contract']=engine.prior.contracts.expected_contract(spec,binding)
        r,intervals,health=execute(c,spec,cp,binding,4096)
        cmp=parent.old.prior.compare_results(reference['result'],r,spec,d['limits'])
        passed=health['passed'] and cmp['passed'] and r['status']=='present_at_horizon'
        api.write(folder/(c['id']+'.json'),{'passed':passed,'result':r,'rows':intervals,'checks':health,'comparison':cmp},raw=True)
        rows.append({'case':c['id'],'passed':passed});print('PILOT',c['id'],passed,flush=True)
    api.write(folder/'completion.json',{'passed':all(x['passed'] for x in rows),'cases':rows,'artifacts':{str(p):api.sha(p) for p in folder.glob('*.json')}})
    return all(x['passed'] for x in rows)


def worker(name):
    d=api.read(DESIGN);verify(d)
    c=next(x for x in d['cases'] if x['id']==name);spec=c['spec']
    folder=RUN/name;folder.mkdir(parents=True,exist_ok=False)
    api.write(folder/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'design_sha256':api.sha(DESIGN)})
    parent.old.prior.prior.configure();hot.warmup()
    cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint']);initial=copy.deepcopy(cp)
    binding=api.digest([d['binding'],name]);cp['contract']=engine.prior.contracts.expected_contract(spec,binding)
    initial=copy.deepcopy(cp);ledger=[];start=time.perf_counter();failure=None
    for i in range(1,d['budget']['max_segments_per_case']+1):
        if time.perf_counter()-start+45>d['budget']['case_wall_s']:break
        segment=folder/f'segment_{i:02d}';segment.mkdir(exist_ok=False)
        before=copy.deepcopy(cp);r,rows,checks=execute(c,spec,cp,binding,30000)
        progress=guard.assess(before['state']['t'],r['time_s'],spec['horizon_s'],spec['config']['numerics']['max_dt_s'],
                              'incomplete_budget' if r['status']=='paused_checkpoint' else r['status'])
        with gzip.open(segment/'intervals.json.gz','xb',compresslevel=1) as f:f.write(json.dumps(rows,sort_keys=True,allow_nan=False).encode())
        record={'result':r,'checks':checks,'progress':progress,'input_checkpoint_sha256':api.digest(before),
                'previous_record_sha256':ledger[-1]['sha256'] if ledger else None,'intervals_sha256':api.sha(segment/'intervals.json.gz'),
                'design_sha256':api.sha(DESIGN),'binding':binding}
        api.write(segment/'record.json',record,raw=True);api.write(segment/'completion.json',{'record_sha256':api.sha(segment/'record.json')})
        ledger.append({'path':str(segment/'record.json'),'sha256':api.sha(segment/'record.json'),'passed':checks['passed'],'time_s':r['time_s'],'status':r['status']})
        print(name,i,checks['passed'],r['status'],r['time_s'],flush=True)
        cp=r['checkpoint']
        if not checks['passed'] or r['status'] not in ('paused_checkpoint','incomplete_budget','present_at_horizon','full_window_exit'):
            failure='health_or_solver_failure';break
        if r['status'] in ('present_at_horizon','full_window_exit'):break
        if not progress['continue']:failure='no_useful_progress';break
    verify(d)
    completed=bool(ledger and r['status']=='present_at_horizon' and r['time_s']==spec['horizon_s'])
    result={'case':name,'passed':completed and failure is None and all(x['passed'] for x in ledger),'segments':ledger,
            'completed_horizon':completed,'failure':failure,'budget_exhausted':not completed and failure is None,
            'new_steps':r['steps']-initial['state']['steps'],'new_rejections':r['rejected']-initial['state']['rejected'],
            'wall_s':time.perf_counter()-start,'spec':spec,'design_sha256':api.sha(DESIGN),'initial_checkpoint':initial}
    api.write(folder/'results.json',result,raw=True);api.write(folder/'completion.json',{'results_sha256':api.sha(folder/'results.json'),'passed':result['passed']})
    return 0 if result['passed'] else 4


def path_data(records,initial,spec,stage149=False):
    history=[{'time_s':initial['state']['t'],'position_m':initial['state']['x'],'orientation':initial['state']['p'],'velocity_generalized':initial['state']['q']}]
    previous_cp=initial;previous_sha=None;all_ok=True;support=set();max_dt=0.;cert_count=0;energy=0
    for item in records:
        p=Path(item['path']);record=api.read(p);r=record['result']
        api.require(api.sha(p)==item['sha256']==api.read(p.parent/'completion.json')['record_sha256'],'record hash')
        api.require(api.sha(p.parent/'intervals.json.gz')==record['intervals_sha256'],'interval hash')
        api.require(record['input_checkpoint_sha256']==api.digest(previous_cp) and record['previous_record_sha256']==previous_sha,'checkpoint link')
        with gzip.open(p.parent/'intervals.json.gz','rt') as f:rows=json.load(f)
        ck=audit.clock_chain(previous_cp['state']['t'],rows,r['time_s'])
        h=engine.prior.reference.independent_health(r,spec)
        certificate=record['contact_certificates'] if stage149 else record['checks']['contact_certificates']
        all_ok &= ck['passed'] and h['passed'] and certificate['all_passed'] and not r.get('stage119_repair_calls')
        cert_count+=certificate['count'];energy+=certificate['legacy_energy_gate_violations']
        max_dt=max(max_dt,max(x['dt_s'] for x in rows))
        support.update(tuple(x['supported_bearing_ids']) for x in rows)
        history.extend(rows);previous_cp=r['checkpoint'];previous_sha=api.sha(p)
    arrays={k:np.asarray([x[k] for x in history],float) for k in ('time_s','position_m','orientation','velocity_generalized')}
    return arrays,r,{'passed':bool(all_ok),'max_dt_s':max_dt,'support_sets':sorted(support),'contact_certificates':cert_count,'legacy_energy_violations':energy}


def evaluate(d):
    OUT.mkdir(parents=True,exist_ok=False)
    ref_ev=api.read(previous.OUT/'results.json');ref_spec=api.read(previous.RUN/'protocol.json')['spec']
    c=d['cases'][0];initial=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
    initial['contract']=engine.prior.contracts.expected_contract(ref_spec,api.read(previous.RUN/'launch.json')['binding'])
    ref,ref_final,ref_checks=path_data(ref_ev['segments'],initial,ref_spec,True)
    comparisons=[]
    for c in d['cases']:
        folder=RUN/c['id'];ev=api.read(folder/'results.json')
        api.require(api.sha(folder/'results.json')==api.read(folder/'completion.json')['results_sha256'],'worker completion')
        arrays,last,checks=path_data(ev['segments'],ev['initial_checkpoint'],c['spec'])
        cmp=parent.old.prior.compare_results(ref_final,last,c['spec'],d['limits'])
        common=np.unique(np.concatenate([ref['time_s'],arrays['time_s']]))
        whole={}
        for key,limit_key,scale in [('position_m','position_over_b',c['spec']['config']['prolate_semiaxes_m'][1]),
                                    ('orientation','axis_vector_norm',1.),
                                    ('velocity_generalized','generalized_velocity_relative',c['spec']['config']['target_mean_interstitial_velocity_m_s'])]:
            interp=lambda a:np.column_stack([np.interp(common,a['time_s'],a[key][:,j]) for j in range(a[key].shape[1])])
            difference=np.linalg.norm(interp(arrays)-interp(ref),axis=1)/scale
            whole[limit_key]=float(np.max(difference))
        event_tolerance=2*max(ref_checks['max_dt_s'],checks['max_dt_s'])
        event_error=abs(last['first_contact_dwell_time_s']-ref_final['first_contact_dwell_time_s'])
        verdict=(last['status']==ref_final['status'] and last['persistent_contact_observed']==ref_final['persistent_contact_observed'] and last['trap_state']['trapped']==ref_final['trap_state']['trapped'])
        passed=(ev['passed'] and ref_checks['passed'] and checks['passed'] and cmp['passed'] and verdict and event_error<=event_tolerance
                and all(whole[k]<=d['limits'][k] for k in whole) and checks['support_sets']==ref_checks['support_sets'])
        comparisons.append({'case':c['id'],'passed':bool(passed),'factor':c['factor'],'kappa':c['kappa'],
                            'final':cmp,'whole_continuation':whole,'dwell_event_error_s':event_error,'dwell_event_tolerance_s':event_tolerance,
                            'same_verdict':verdict,'checks':checks,'new_steps':ev['new_steps'],'new_rejections':ev['new_rejections'],'wall_s':ev['wall_s']})
        print('COMPARISON',c['id'],passed,whole,flush=True)
    verify(d)
    result={'stage':'Stage150','passed':all(x['passed'] for x in comparisons),'comparisons':comparisons,'reference_checks':ref_checks,
            'claim':d['claim_boundary'],'design_sha256':api.sha(DESIGN),'reference_sha256':api.sha(previous.OUT/'results.json'),
            'artifact_hashes':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()}}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('STAGE150_PASS',result['passed'],flush=True)
    return 0 if result['passed'] else 4


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'design_sha256':api.sha(DESIGN),'argv':sys.argv})
    if not pilot(d):raise RuntimeError('pilot failed; no full dispatch')
    def launch(c):
        with (RUN/(c['id']+'.stdout.txt')).open('x') as out,(RUN/(c['id']+'.stderr.txt')).open('x') as err:
            child=subprocess.run([sys.executable,'-B','-u',__file__,'worker',c['id']],stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        print('FINISHED',c['id'],child.returncode,flush=True);return child.returncode
    with ThreadPoolExecutor(max_workers=4) as pool:codes=list(pool.map(launch,d['cases']))
    api.write(RUN/'dispatch_completion.json',{'return_codes':codes,'all_workers_exited':True})
    # Preserve partial and failed runs for analysis; no automatic retry.
    if any(codes):raise RuntimeError('one or more bounded workers did not qualify')
    return evaluate(d)


if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':prepare()
        elif sys.argv[1]=='run':raise SystemExit(run())
        elif sys.argv[1]=='worker':raise SystemExit(worker(sys.argv[2]))
        elif sys.argv[1]=='evaluate':raise SystemExit(evaluate(api.read(DESIGN)))
        else:raise ValueError('unknown command')
    except Exception as exc:
        target=(RUN/sys.argv[2]) if len(sys.argv)>2 and sys.argv[1]=='worker' else RUN
        if target.exists() and not (target/'failure.json').exists():api.write(target/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise
