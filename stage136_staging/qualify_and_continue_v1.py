"""Bounded compiled-sweep qualification and gated continuation of Stage135."""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import copy
import os
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage135_staging'))
import extend_matched_transport_v1 as prior
import compiled_scalar_v1 as hot
import inertial_contact_scalar_kernel_v1 as scalar_scope

api,engine=prior.api,prior.engine
BASE='compiled_contact_continuation_20260918'
DESIGN=ROOT/'stage136_designs'/BASE/'design_01.json'
RUN=ROOT/'stage136_runs'/BASE
EVAL=ROOT/'stage136_evaluations'/BASE


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design drift')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    prior.verify(api.read(prior.DESIGN))
    api.require(d['physical_changes']==[],'physics drift')


def prepare():
    pd=api.read(prior.DESIGN);prior.verify(pd)
    seal=prior.EVAL/'independent_evaluation_01/completion.json'
    evidence=prior.EVAL/'independent_evaluation_01/results.json'
    ev=api.read(evidence)
    api.require(ev['source_and_checkpoint_audit_passed'] and ev['all_health_passed'] and ev['no_failure_or_stderr'],'prior audit required')
    api.require(api.read(seal)['results_sha256']==api.sha(evidence),'prior seal')
    cases=[];inputs={str(p):api.sha(p) for p in [prior.DESIGN,seal,evidence,prior.RUN/'completion.json']}
    for shape,segments in [('sphere',[1,8,12]),('fibre',[10,11])]:
        c=next(c for c in pd['cases'] if f'_{shape}_' in c['id'])
        for segment in segments:
            record=prior.RUN/c['id']/f'segment_{segment:02d}/record.json'
            completion=record.parent/'completion.json'
            api.require(api.read(completion)['record_sha256']==api.sha(record),'source record checksum')
            cp=api.read(record)['result']['checkpoint']
            api.require(cp['state_sha256']==api.digest(cp['state']),'source state')
            pending=cp['state']['pending_trial']
            api.require(pending is None or (pending['time_s']==cp['state']['t'] and pending['dt_s']>0 and pending['attempt']>=0),'source pending retry')
            cases.append({'id':f'{shape}_{segment:02d}','shape':shape,'source':str(record),'spec':c['spec'],'state_sha256':cp['state_sha256']})
            inputs.update({str(record):api.sha(record),str(completion):api.sha(completion)})
    paths={Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents and 'deps' not in Path(m.__file__).parts}
    paths.update(Path(__file__).parent.glob('*.py'))
    paths.add(hot.abi.BLAS_PATH)
    # Bind installed compiler sources/binaries and Python executable, no installation.
    for folder in [ROOT/'bottleneck_resolution_20260912/deps/numba',ROOT/'bottleneck_resolution_20260912/deps/llvmlite',ROOT/'bottleneck_resolution_20260912/deps/llvmlite.libs']:
        paths.update(p for p in folder.rglob('*') if p.is_file() and p.suffix in ['.py','.pyd','.dll'])
    paths.add(Path(sys.executable))
    d={'stage':'Stage136','physical_changes':[],
       'question':'Can compiling only cold contact sweeps reduce cost while reproducing the current repaired scalar solver and inherited complete checkpoint state?',
       'cases':cases,'replay_accepted_steps':4,
       'acceptance':{'position_over_b':1e-8,'axis_vector_norm':1e-8,'generalized_velocity_relative':1e-7,'clock_s':1e-12,
                     'same_accepted_rejected_counts':True,'same_active_contact_sequence':True,'independent_health':True,
                     'minimum_aggregate_warmed_replay_speedup':1.2,'primitive_velocity_relative':1e-8},
       'continuation':{'case_ids':['sphere_12','fibre_11'],'segments_per_case':4,'segment_integrator_s':45,'stage_dispatch_wall_s':450,
                       'target_s':pd['cases'][0]['spec']['horizon_s'],'require_all_qualification_checks':True},
       'boundaries':'Two conditional seed-2 near-outlet states only. Preserve all physical fields and histories. No GPU job, population campaign, calibration, new physics, retention inference or full-path convergence claim. Failure stops promotion; budget-incomplete is unresolved.',
       'backend':{'numpy':hot.np.__version__,'numba':__import__('numba').__version__,'blas':hot.abi.BLAS_CONFIGURATION,'primary_expanded_source':hot.PRIMARY_SOURCE},
       'sources':{str(p):api.sha(p) for p in sorted(paths)},'inputs':inputs}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def checkpoint(d,c):
    cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
    api.require(cp['state_sha256']==c['state_sha256']==api.digest(cp['state']),'source state drift')
    bound=api.digest([d['binding'],c['id']])
    cp['contract']=engine.prior.contracts.expected_contract(c['spec'],bound)
    return cp,bound


@contextmanager
def capture(rows):
    original=(hot.s50._solve,hot.scalar.sor_solve)
    def wrap(kind,fn):
        def traced(*args):
            data=[np.tolist() if hasattr(np,'tolist') else np for np in args]
            started=time.perf_counter();row={'kind':kind,'args':data}
            try:
                q,h=fn(*args);row.update(accepted=True,velocity=q.tolist(),health=copy.deepcopy(h))
                return q,h
            except (RuntimeError,ValueError) as exc:
                row.update(accepted=False,error=str(exc));raise
            finally:
                row['wall_s']=time.perf_counter()-started;rows.append(row)
        return traced
    hot.s50._solve=wrap('pgs',original[0]);hot.scalar.sor_solve=wrap('sor',original[1])
    try:yield
    finally:hot.s50._solve,hot.scalar.sor_solve=original


def replay(name,mode):
    d=api.read(DESIGN);verify(d);prior.configure();c=next(c for c in d['cases'] if c['id']==name)
    out=RUN/'replay_01'/name/mode;out.mkdir(parents=True,exist_ok=False)
    api.write(out/'launch.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN)})
    cp,bound=checkpoint(d,c);trace=[]
    startup=hot.warmup() if mode=='compiled' else 0.
    try:
        with hot.scope() if mode=='compiled' else nullcontext():
            with capture(trace):
                result,intervals=engine.runtime.execute(c['spec'],bound,checkpoint=cp,pause=cp['state']['steps']+d['replay_accepted_steps'])
        verify(d);health=engine.prior.reference.independent_health(result,c['spec'])
        api.write(out/'trace.json',trace,raw=True)
        api.write(out/'intervals.json',intervals,raw=True)
        api.write(out/'record.json',{'case_id':name,'mode':mode,'design_sha256':api.sha(DESIGN),'checkpoint_input_sha256':api.digest(cp),'result':result,'health':health,'startup_s':startup,'trace_sha256':api.sha(out/'trace.json'),'intervals_sha256':api.sha(out/'intervals.json')},raw=True)
        api.write(out/'completion.json',{'record_sha256':api.sha(out/'record.json'),'launch_sha256':api.sha(out/'launch.json')})
        okay=health['passed'] and result['status']=='paused_checkpoint' and len(intervals)==d['replay_accepted_steps']
        if not okay:api.write(out/'failure.json',{'status':result['status'],'health':health})
        print(name,mode,result['status'],result['runtime_seconds'],len(trace),flush=True)
        return 0 if okay else 4
    except Exception as exc:
        api.write(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()});raise


def run_replays():
    d=api.read(DESIGN);verify(d);out=RUN/'replay_01';out.mkdir(parents=True,exist_ok=False)
    for c in d['cases']:
        for mode in ['reference','compiled']:
            with (out/(c['id']+'_'+mode+'.stdout.txt')).open('x') as stdout,(out/(c['id']+'_'+mode+'.stderr.txt')).open('x') as stderr:
                child=subprocess.run([sys.executable,'-B','-u',__file__,'replay',c['id'],mode],stdout=stdout,stderr=stderr)
            print(c['id'],mode,'exit',child.returncode,flush=True)
            if child.returncode:raise RuntimeError('replay failed; preserved')
    api.write(out/'completion.json',{'design_sha256':api.sha(DESIGN),'case_order':[c['id'] for c in d['cases']]})


def compare_results(a,b,spec,limits):
    np=api.np;minor=spec['config']['prolate_semiaxes_m'][1]
    pos=float(np.linalg.norm(np.array(a['position_m'])-b['position_m'])/minor)
    axis=float(np.linalg.norm(np.array(a['orientation'])-b['orientation']))
    velocity=float(np.linalg.norm(np.array(a['velocity_generalized'])-b['velocity_generalized'])/max(np.linalg.norm(a['velocity_generalized']),spec['config']['target_mean_interstitial_velocity_m_s']))
    clock=abs(a['time_s']-b['time_s'])
    return {'position_over_b':pos,'axis_vector_norm':axis,'generalized_velocity_relative':velocity,'clock_s':clock,
            'passed':pos<=limits['position_over_b'] and axis<=limits['axis_vector_norm'] and velocity<=limits['generalized_velocity_relative'] and clock<=limits['clock_s']}


def solve_one(kind,args,compiled):
    args=[api.np.array(x) if i<4 else x for i,x in enumerate(args)]
    try:
        with hot.scope() if compiled else nullcontext():
            fn=hot.s50._solve if kind=='pgs' else hot.scalar.sor_solve
            q,h=scalar_scope._scoped(fn,*args)
        return {'accepted':True,'q':q,'h':h,'independent':engine.local.independent_contact(*args[:6],q,h)}
    except (RuntimeError,ValueError) as exc:
        return {'accepted':False,'error':str(exc)}


def qualify():
    d=api.read(DESIGN);verify(d);out=EVAL/'qualification_01';out.mkdir(parents=True,exist_ok=False)
    limits=d['acceptance'];pairs=[];systems={};artifacts={};ref_total=fast_total=0.
    for c in d['cases']:
        saved=[]
        for mode in ['reference','compiled']:
            folder=RUN/'replay_01'/c['id']/mode
            r=api.read(folder/'record.json');seal=api.read(folder/'completion.json')
            api.require(seal['record_sha256']==api.sha(folder/'record.json') and seal['launch_sha256']==api.sha(folder/'launch.json'),'replay seal')
            api.require(r['design_sha256']==api.sha(DESIGN) and r['checkpoint_input_sha256']==api.digest(checkpoint(d,c)[0]),'replay binding')
            for name,key in [('trace.json','trace_sha256'),('intervals.json','intervals_sha256')]:api.require(r[key]==api.sha(folder/name),'replay artifact')
            for p in folder.iterdir():
                if p.is_file():artifacts[str(p)]=api.sha(p)
            api.require(engine.prior.reference.independent_health(r['result'],c['spec'])==r['health'],'independent health mismatch')
            saved.append((r,api.read(folder/'intervals.json')))
        (a,ar),(b,br)=saved
        check=compare_results(a['result'],b['result'],c['spec'],limits)
        equal_decisions=all(a['result'][k]==b['result'][k] for k in ['status','steps','rejected','contact_solver_retries','persistent_contact_observed'])
        intervals_ok=len(ar)==len(br)==d['replay_accepted_steps'] and all(compare_results(x,y,c['spec'],limits)['passed'] and x['dt_s']==y['dt_s'] and x['active_contact_ids']==y['active_contact_ids'] and x['supported_bearing_ids']==y['supported_bearing_ids'] for x,y in zip(ar,br))
        check.update(case=c['id'],same_decisions=equal_decisions,intervals_passed=intervals_ok,reference_s=a['result']['runtime_seconds'],compiled_s=b['result']['runtime_seconds'],checkpoint_state_exact=a['result']['checkpoint']['state']==b['result']['checkpoint']['state'])
        check['passed'] &= equal_decisions and intervals_ok and a['health']['passed'] and b['health']['passed']
        pairs.append(check);ref_total+=check['reference_s'];fast_total+=check['compiled_s']
        trace=api.read(RUN/'replay_01'/c['id']/'reference/trace.json')
        # Prospective selection: first and three slowest per solver per pose.
        for kind in ['pgs','sor']:
            selected=[x for x in trace if x['kind']==kind]
            for row in selected[:1]+sorted(selected,key=lambda x:x['wall_s'],reverse=True)[:3]:
                systems[api.digest([kind,row['args']])]=(kind,row['args'])
    warm=hot.warmup();primitives=[]
    toys=[('stick',[-1,.1,0,0,0,0],0,.3),('slip',[-1,1,0,0,0,0],0,.3),('open',[1,.2,0,0,0,0],0,.3),('separated',[-1,.1,0,0,0,0],2,.3),('frictionless',[-1,1,0,0,0,0],0,0),('closure',[-1,1,0,0,0,0],.2,.3),('penetration',[-1,1,0,0,0,0],-.2,.3)]
    for name,v,g,mu in toys:
        for scale in [1.,1e-7,1e3]:
            args=[api.np.asarray(v)*scale,api.np.eye(6),api.np.c_[api.np.eye(3),api.np.zeros((3,3))],api.np.array([g*scale]),1.,mu,1e-10,25000]
            for kind in ['pgs','sor']:systems['toy_'+name+'_'+str(scale)+'_'+kind]=(kind,api.normalized(args))
    for key,(kind,args) in systems.items():
        a,b=solve_one(kind,args,False),solve_one(kind,args,True)
        same=a['accepted']==b['accepted'];err=None
        if a['accepted'] and b['accepted']:
            err=float(api.np.linalg.norm(a['q']-b['q'])/max(api.np.linalg.norm(args[0]),1e-15))
            passed=same and err<=limits['primitive_velocity_relative'] and a['independent'] and b['independent']
        else:passed=same and a.get('error')==b.get('error')
        primitives.append({'id':key,'kind':kind,'reference':api.normalized(a),'compiled':api.normalized(b),'velocity_relative':err,'passed':passed})
    guards=[]
    for mutation in ['nan','shape','zero_dt','negative_mu','negative_steps','noncontiguous']:
        args=[api.np.eye(3),api.np.array([-1.,.2,0]),api.np.zeros(1),.01,.3,api.np.ones(1),1.,1e-10,25000]
        if mutation=='nan':args[1][0]=float('nan')
        if mutation=='shape':args[0]=api.np.eye(2)
        if mutation=='zero_dt':args[3]=0.
        if mutation=='negative_mu':args[4]=-.3
        if mutation=='negative_steps':args[5][0]=-1.
        if mutation=='noncontiguous':args[0]=api.np.eye(3).T
        rejected=False
        try:hot.phase(*args)
        except ValueError:rejected=True
        guards.append({'test':mutation,'rejected':rejected})
    speed=ref_total/fast_total
    clean=not list((RUN/'replay_01').rglob('failure.json')) and not any(p.stat().st_size for p in (RUN/'replay_01').glob('*.stderr.txt'))
    result={'passed':all(x['passed'] for x in pairs+primitives) and all(x['rejected'] for x in guards) and clean and speed>=limits['minimum_aggregate_warmed_replay_speedup'],
            'pairs':pairs,'primitives':primitives,'guards':guards,'warmed_speedup':speed,'reference_total_s':ref_total,'compiled_total_s':fast_total,'warmup_s':warm,'no_failure_or_stderr':clean,'artifacts':artifacts,
            'scope':'Local implementation qualification, not full-path numerical convergence or physical validation.'}
    verify(d);api.write(out/'results.json',result,raw=True)
    api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'design_sha256':api.sha(DESIGN)})
    print('QUALIFICATION',result['passed'],'speedup',speed,'pairs',[x['passed'] for x in pairs],'primitive_failures',[x['id'] for x in primitives if not x['passed']],flush=True)


def qualified(d):
    p=EVAL/'qualification_01/results.json';s=EVAL/'qualification_01/completion.json'
    api.require(api.read(s)['results_sha256']==api.sha(p) and api.read(s)['design_sha256']==api.sha(DESIGN),'qualification seal')
    q=api.read(p);api.require(q['passed'],'compiled implementation not qualified')
    api.verify_mapping(q['artifacts'])
    return api.sha(p)


def continuation_worker(name,segment):
    d=api.read(DESIGN);verify(d);qualification_hash=qualified(d);prior.configure()
    api.require(name in d['continuation']['case_ids'] and 1<=segment<=d['continuation']['segments_per_case'],'outside continuation design')
    c=next(c for c in d['cases'] if c['id']==name);cp,bound=checkpoint(d,c)
    out=RUN/'continuation_01'/name/f'segment_{segment:02d}';previous_hash=None
    if segment>1:
        p=out.parent/f'segment_{segment-1:02d}/record.json';old=api.read(p);previous_hash=api.sha(p)
        api.require(api.read(p.parent/'completion.json')['record_sha256']==previous_hash and old['result']['status']=='incomplete_budget','previous continuation')
        cp=old['result']['checkpoint']
    api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==engine.prior.contracts.expected_contract(c['spec'],bound),'checkpoint contract')
    out.mkdir(parents=True,exist_ok=False)
    api.write(out/'launch.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN)})
    startup=hot.warmup()
    try:
        with hot.scope():r,intervals=engine.runtime.execute(c['spec'],bound,checkpoint=cp)
        verify(d);health=engine.prior.reference.independent_health(r,c['spec'])
        api.write(out/'intervals.json',intervals,raw=True)
        api.write(out/'record.json',{'case_id':name,'segment':segment,'design_sha256':api.sha(DESIGN),'qualification_sha256':qualification_hash,
                  'previous_record_sha256':previous_hash,'checkpoint_input_sha256':api.digest(cp),'source_record_sha256':api.sha(c['source']),
                  'result':r,'health':health,'startup_s':startup,'compiled_work':dict(hot.work),'intervals_sha256':api.sha(out/'intervals.json')},raw=True)
        api.write(out/'completion.json',{'record_sha256':api.sha(out/'record.json'),'launch_sha256':api.sha(out/'launch.json')})
        okay=health['passed'] and r['status'] in ['incomplete_budget','present_at_horizon','full_window_exit']
        if not okay:api.write(out/'failure.json',{'status':r['status'],'reason':r.get('reason'),'health':health})
        print(name,segment,r['status'],r['time_s'],r['runtime_seconds'],flush=True)
        return 0 if okay else 4
    except Exception as exc:
        if not (out/'failure.json').exists():api.write(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise


def continue_run():
    d=api.read(DESIGN);verify(d);qualification_hash=qualified(d)
    out=RUN/'continuation_01';out.mkdir(parents=True,exist_ok=False)
    api.write(out/'manifest.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN),'qualification_sha256':qualification_hash,'threads':1})
    started=time.perf_counter();ledger=[];stopped=False
    for name in d['continuation']['case_ids']:
        entry={'case_id':name,'status':'not_run','records':[]}
        for segment in range(1,d['continuation']['segments_per_case']+1):
            if stopped or time.perf_counter()-started+60>d['continuation']['stage_dispatch_wall_s']:break
            stem=name+f'_{segment:02d}'
            with (out/(stem+'.stdout.txt')).open('x') as stdout,(out/(stem+'.stderr.txt')).open('x') as stderr:
                child=subprocess.run([sys.executable,'-B','-u',__file__,'worker',name,str(segment)],stdout=stdout,stderr=stderr)
            p=out/name/f'segment_{segment:02d}/record.json'
            if p.exists():
                r=api.read(p)['result'];entry['records'].append({'path':str(p),'sha256':api.sha(p)});entry['status']=r['status']
                print(name,segment,r['status'],r['time_s'],r['runtime_seconds'],flush=True)
            else:entry['status']='worker_failure'
            if child.returncode:stopped=True;break
            if entry['status']!='incomplete_budget':break
        ledger.append(entry)
    verify(d)
    api.write(out/'completion.json',{'design_sha256':api.sha(DESIGN),'manifest_sha256':api.sha(out/'manifest.json'),'ledger':ledger,'wall_s':time.perf_counter()-started,'stopped_on_failure':stopped})
    print('CONTINUATION_DISPATCH_COMPLETE',not stopped,flush=True)
    return 4 if stopped else 0


def audit():
    d=api.read(DESIGN);verify(d);qh=qualified(d);folder=RUN/'continuation_01'
    done=api.read(folder/'completion.json');rows=[];artifacts={}
    api.require(done['design_sha256']==api.sha(DESIGN) and done['manifest_sha256']==api.sha(folder/'manifest.json'),'dispatch seal')
    api.require([e['case_id'] for e in done['ledger']]==d['continuation']['case_ids'],'case order')
    for entry in done['ledger']:
        c=next(c for c in d['cases'] if c['id']==entry['case_id']);cp,bound=checkpoint(d,c)
        source_t=cp['state']['t'];last_hash=None;total=0.;healthy=True;last=None
        for segment,binding in enumerate(entry['records'],1):
            p=Path(binding['path']);rec=api.read(p);seal=api.read(p.parent/'completion.json')
            api.require(binding['sha256']==api.sha(p)==seal['record_sha256'] and seal['launch_sha256']==api.sha(p.parent/'launch.json'),'record seal')
            api.require(rec['case_id']==c['id'] and rec['segment']==segment and rec['design_sha256']==api.sha(DESIGN) and rec['qualification_sha256']==qh,'record design')
            api.require(rec['previous_record_sha256']==last_hash and rec['checkpoint_input_sha256']==api.digest(cp) and rec['source_record_sha256']==api.sha(c['source']),'record chain')
            r=rec['result'];health=engine.prior.reference.independent_health(r,c['spec'])
            api.require(health==rec['health'],'health audit disagreement')
            intervals=api.read(p.parent/'intervals.json');api.require(rec['intervals_sha256']==api.sha(p.parent/'intervals.json'),'interval artifact')
            api.require(abs(sum(x['dt_s'] for x in intervals)-(r['time_s']-cp['state']['t']))<1e-9,'elapsed time closure')
            if intervals:
                api.require(abs(intervals[-1]['time_s']-r['time_s'])<1e-12 and api.np.allclose(intervals[-1]['position_m'],r['position_m'],rtol=0,atol=1e-13),'endpoint closure')
            cp=r['checkpoint'];api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==engine.prior.contracts.expected_contract(c['spec'],bound),'output checkpoint')
            last_hash=binding['sha256'];total+=r['runtime_seconds'];healthy &= health['passed'];last=r
        rows.append({'case_id':c['id'],'status':entry['status'],'source_time_s':source_t,'time_s':None if last is None else last['time_s'],
                     'pore_volumes':None if last is None else last['time_s']*c['spec']['field_metadata']['pv_per_second'],'integration_s':total,
                     'segments':len(entry['records']),'health_passed':healthy and last is not None,'outlet_passage':last is not None and last['status']=='full_window_exit',
                     'finite_dwell':None if last is None else last['persistent_contact_observed']})
    for p in folder.rglob('*'):
        if p.is_file():artifacts[str(p)]=api.sha(p)
    clean=not done['stopped_on_failure'] and not list(folder.rglob('failure.json')) and not any(p.stat().st_size for p in folder.glob('*.stderr.txt'))
    out=EVAL/'independent_evaluation_01';out.mkdir(parents=True,exist_ok=False)
    result={'source_checkpoint_artifact_audit_passed':True,'all_health_passed':all(r['health_passed'] for r in rows),'no_failure_or_stderr':clean,
            'all_queries_completed':all(r['status'] in ['full_window_exit','present_at_horizon'] for r in rows),'rows':rows,'dispatch_wall_s':done['wall_s'],
            'population_release_fraction':None,'artifacts':artifacts,'claim':'Bounded near-outlet continuation under locally qualified compiled sweeps; no full-path convergence, experimental validation or population release claim.'}
    api.write(out/'results.json',result);api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'design_sha256':api.sha(DESIGN),'qualification_sha256':qh})
    print({k:v for k,v in result.items() if k!='artifacts'},flush=True)


if __name__=='__main__':
    action=sys.argv[1]
    if action=='prepare':prepare()
    elif action=='replays':run_replays()
    elif action=='replay':raise SystemExit(replay(sys.argv[2],sys.argv[3]))
    elif action=='qualify':qualify()
    elif action=='continue':raise SystemExit(continue_run())
    elif action=='worker':raise SystemExit(continuation_worker(sys.argv[2],int(sys.argv[3])))
    elif action=='audit':audit()
    else:raise ValueError(action)
