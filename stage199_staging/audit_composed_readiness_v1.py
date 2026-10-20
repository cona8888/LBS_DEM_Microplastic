"""Independent closure of all ten trajectory bundles and late-history stress.

Every old failure stays visible. A permissive maximum-chunk resource screen
can reject readiness without spending17,000 further trajectory steps. This
screen is a lower estimate WITHIN the retained conservative cost policy, not
a lower bound on physical execution time or a complete six-case forecast.
"""
from pathlib import Path
import hashlib,json,math,os,psutil,sys,traceback
import audit_failure_ledger_v1 as previous
import qualify_composed_boundary_v1 as boundary
import qualify_owned_late_history_v1 as history
api,job,q,WORK=boundary.api,boundary.job,boundary.q,boundary.WORK
DESIGN=WORK.with_name('composed_readiness_audit_01.json');OUT=boundary.OUT.with_name('composed_readiness_audit_01')
PROBES=(*previous.PROBES,boundary.current)
COUNTS=(3580,7406,3580,3580,3580)

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'independent audit binding')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])

def prepare():
    inputs=[WORK,boundary.current.ORACLE,boundary.current.ORACLE.with_suffix('.seal.json'),boundary.p.held.FINE,boundary.p.held.FINE.with_suffix('.seal.json')]
    sources=[Path(__file__),Path(q.__file__),Path(job.kernel.evaluate.__code__.co_filename.split('::')[0]),Path(previous.__file__),Path(boundary.__file__),Path(history.__file__)]
    for probe in (*PROBES,boundary):
        probe.verify(api.read(probe.DESIGN));sources.append(Path(probe.__file__));inputs.append(probe.DESIGN)
        inputs.extend(x for x in probe.RUN.iterdir() if x.is_file());inputs.extend(x for x in probe.OUT.iterdir() if x.is_file())
    history.verify(api.read(history.DESIGN));inputs.append(history.DESIGN)
    inputs.extend(x for x in history.RUN.iterdir() if x.is_file());inputs.extend(x for x in history.OUT.iterdir() if x.is_file())
    p={'stage':'Stage199 independent composed implementation and resource closure','prior_recovery_steps':53086,'expected_prefix_counts':list(COUNTS),'expected_boundary_steps':3676,'cumulative_recovery_steps':78488,
       'expected_failed_candidate':'native_prefix_01','first_different_row':2995,'new_trajectory_steps':0,'production_authorized':False,
       'resource_screen':'Keep original1.3 margin and full80,000-row child write+state-hash cost charged to every record, as in the preserved Stage197 conservative policy. Give the current fine case the most favorable allowed10,000 accepted steps per record; include no other cases, auditor queuing, startup or slowdown. Failure of this screen blocks full-preflight spending; passing would not establish production readiness.',
       'sources':{str(x):api.sha(x) for x in sources},'inputs':{str(x):api.sha(x) for x in inputs}}
    p['binding']=api.digest(p);job.commit(DESIGN,p);verify(p);print('COMPOSED_READINESS_AUDIT_PROTOCOL',api.sha(DESIGN),flush=True)

def reference(path,record,design):
    rows=record['result']['history'];b=json.dumps(rows,separators=(',',':'),allow_nan=True).encode()
    return {'path':str(path.resolve()),'design_sha256':design,'compressed_sha256':api.sha(path),'original_sha256':hashlib.sha256(q.canonical(record)).hexdigest(),'history_sha256':hashlib.sha256(b).hexdigest(),'history_length':len(rows)}

def physical(d,case,rec,before,design):
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        geo=boundary.p.pre.prior.geometry()
        r=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),before,geo,design,d['minimum_gap_semantics'])
    api.require(r['passed'] and not rec['result']['rejected'],'original independent physical/clock/health/balance gates');return r

def run():
    p=api.read(DESIGN);verify(p);w=api.read(WORK)
    api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work clock')
    api.require(not any(x.pid!=os.getpid() and 'python' in (x.info['name'] or '').lower() and 'matdem_microplastic' in ' '.join(x.info['cmdline'] or []).lower() for x in psutil.process_iter(['name','cmdline'])),'no other owned worker')
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(DESIGN)})
    try:
        job.parent.b.old.parent.configure();oracle=q.independent_file(boundary.current.ORACLE,api.sha(boundary.current.template.old.DESIGN));reports=[];total=0;latest=None
        for probe,n in zip(PROBES,COUNTS):
            d=api.read(probe.DESIGN);probe.verify(d);sha=api.sha(probe.DESIGN);path=probe.RUN/'serial.json.xz';rec=q.independent_file(path,sha)
            account=api.read(path.with_suffix('.accounting.json'));api.require(len(rec['rows'])==account['accepted_steps']==n and account['raw_sha256']==api.sha(path),'exact independent raw accounting')
            case=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125');check=physical(d,case,rec,api.read(probe.RUN/'initial.json'),sha)
            exact=q.canonical(rec['rows'][:3580])==q.canonical(oracle['rows']);state=q.canonical(rec['result']['checkpoint']['state'])==q.canonical(oracle['result']['checkpoint']['state'])
            if probe is previous.latest:
                first=next(i for i,(a,b) in enumerate(zip(rec['rows'],oracle['rows'])) if a!=b);f=api.read(probe.OUT/'failure.json')
                api.require(not exact and not state and first==2995 and f['known_new_accepted_steps']==3580 and not f['accepted_step_accounting_unresolved'],'original identity failure remains rejected')
                status='rejected_exact_identity'
            else:
                r=api.read(probe.OUT/'results.json');api.require(r['passed'] and api.read(probe.OUT/'completion.json')['results_sha256']==api.sha(probe.OUT/'results.json'),'sealed qualified result')
                api.verify_mapping(r['artifacts']);api.require(exact and (probe is previous.long or state),'all saved exact rows and fixed-cap state')
                span=check['stop_s']-check['start_s'];factor=case['spec']['horizon_s']*w['runtime_and_storage_margin']/span/3600
                api.require(span==r['simulated_seconds'] and r['compute_seconds']==rec['compute_call_wall_s'] and r['transaction_seconds']*factor==r['fine_transaction_hours_with_margin'],'unchanged measured time/margin arithmetic')
                status='healthy_censored_prefix' if probe is previous.long else 'exact_local_prefix'
                if probe is boundary.current:latest=rec
            total+=n;reports.append({'name':probe.RUN.name,'accepted_steps':n,'status':status,'exact_known_prefix':exact,'exact_fixed_cap_state':state,'original_numerical_audit':check,'raw_sha256':api.sha(path)})
            print('INDEPENDENT_PREFIX',probe.RUN.name,n,status,flush=True)
        d=api.read(boundary.DESIGN);boundary.verify(d);sha=api.sha(boundary.DESIGN);old=q.independent_file(boundary.p.held.FINE,api.sha(boundary.p.pre.job.DESIGN))
        pending=boundary.tests.boundary(latest,old);case=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125');records={};br=[]
        for name,cap in d['calls'].items():
            path=boundary.RUN/(name+'.json.xz');a=api.read(path.with_suffix('.accounting.json'));prefix=records.get('split_a') if name=='split_b' else None
            ref=reference(boundary.RUN/'split_a.json.xz',prefix,sha) if prefix is not None else None
            rec=q.independent_file(path,sha,prefix['result']['history'] if prefix is not None else None,ref)
            if name=='split_a':before=api.read(boundary.RUN/'initial.json')
            elif name=='split_b':before=records['split_a']['result']['checkpoint']
            else:before=boundary.tests.rebind(d,case,(latest if name=='paused_candidate' else old)['result']['checkpoint'])
            api.require(len(rec['rows'])==a['accepted_steps']==cap and a['raw_sha256']==api.sha(path),'boundary raw/cap accounting')
            check=physical(d,case,rec,before,sha);records[name]=rec
            if name.startswith('split_'):
                expected=latest['rows'][:1790] if name=='split_a' else latest['rows'][1790:]
                api.require(q.canonical(rec['rows'])==q.canonical(expected),'exact original partition rows')
                if name=='split_b':api.require(q.canonical(rec['result']['checkpoint']['state'])==q.canonical(latest['result']['checkpoint']['state']),'exact full partition checkpoint')
            else:
                control=records['old_pending_baseline'];api.require(rec['rows'][0]['dt_s']==pending['dt_s'] and q.canonical(rec['rows'])==q.canonical(control['rows']) and q.canonical(rec['result']['checkpoint']['state'])==q.canonical(control['result']['checkpoint']['state']),'original pending timestep and full baseline/candidate identity')
            total+=cap;br.append({'name':name,'accepted_steps':cap,'raw_sha256':api.sha(path),'audit':check});print('INDEPENDENT_BOUNDARY',name,cap,flush=True)
        hr=api.read(history.OUT/'results.json');api.require(hr['passed'] and api.read(history.OUT/'completion.json')['results_sha256']==api.sha(history.OUT/'results.json'),'sealed synthetic history qualification');api.verify_mapping(hr['artifacts'])
        hs=api.sha(history.DESIGN);parent=None;ref=None;history_reports=[]
        for name,n in zip(('bootstrap','parent','child'),(79920,79960,80000)):
            path=history.RUN/(name+'.json.xz');rec=q.independent_file(path,hs,parent,ref)
            api.require(rec['synthetic_resource_fixture_only'] and rec['result']['status']=='synthetic_resource_fixture' and len(rec['result']['history'])==n,'explicit nonphysical history fixture')
            api.require(api.digest(rec['result']['checkpoint']['state'])==rec['result']['checkpoint']['state_sha256'],'original complete synthetic checkpoint hash')
            parent=rec['result']['history'];ref=reference(path,rec,hs);history_reports.append({'name':name,'history_rows':n,'raw_sha256':api.sha(path)});print('INDEPENDENT_HISTORY',name,n,flush=True)
        accounts=list(boundary.RUN.parent.glob('*/*.accounting.json'));launches=list(boundary.RUN.parent.glob('*/*.launch.json'))
        api.require(len(accounts)==len(launches)==10 and sum(api.read(x)['accepted_steps'] for x in accounts)==total and total+53086==78488,'no unresolved or extra trajectory reservation')
        fine=api.read(boundary.current.OUT/'results.json');fd=api.read(boundary.current.DESIGN);fc=next(c for c in fd['cases'] if c['id']=='s2_i0_fibre_f0p03125')
        dt=fine['simulated_seconds']/fine['new_accepted_steps'];steps=math.ceil(fc['spec']['horizon_s']/dt);cap=fd['budget']['step_cap_per_call'];count=math.ceil(steps/cap);late=hr['measurements'][-1]
        api.require(steps<=fc['step_ceiling'] and cap==10000,'unchanged horizon, timestep and most favorable allowed full chunk')
        extra=count*(late['write_seconds']+late['state_hash_seconds'])*w['runtime_and_storage_margin']/3600
        hours=fine['fine_transaction_hours_with_margin']+extra;available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        screen={'case':fc['id'],'planning_steps':steps,'maximum_allowed_steps_per_record':cap,'minimum_records_at_maximum_chunk':count,'short_history_transaction_hours_with_margin':fine['fine_transaction_hours_with_margin'],'late_history_extra_hours_with_margin':extra,'producer_only_hours_with_margin':hours,'available_simulation_hours':available,'runtime_gate_passed':hours<=available,'all_other_cases_auditor_startup_and_slowdown_omitted':True,'full_six_case_forecast':False,'claim':'Optimistic lower estimate within the retained conservative measured-regime policy only; not a hard physical/runtime lower bound or completion promise.'}
        verify(p)
        result={'status':'qualified_local_implementation_resource_blocked' if hours>available else 'local_qualification_ready_for_full_preflight','evidence_and_accounting_passed':True,'all_candidates_passed':False,'failed_candidate_preserved':'native_prefix_01','new_trajectory_steps':0,'stage199_accepted_steps':total,'cumulative_recovery_steps':78488,'remaining_recovery_steps':21512,'no_unresolved_reservation':True,'no_other_owned_worker':True,'prefixes':reports,'boundary':br,'synthetic_history':history_reports,'resource_screen':screen,'full_preflight_run':False,'production_authorized':False,'complete_observations':0,'protocol_sha256':api.sha(DESIGN)}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('COMPOSED_READINESS_CLOSED',78488,'runtime_hours',hours,'available',available,flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
