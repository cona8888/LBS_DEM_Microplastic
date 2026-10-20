"""20,000-step local repair regression, separate from campaign preflight.

The prepared combined 38,200-step preflight was not executed: it would exceed
the original campaign's inclusive 20,000-step allowance. This component is
charged to the four-hour repair budget; any later fresh campaign retains its
original separate preflight/production budget, with both totals disclosed.
"""
from pathlib import Path
import copy
import os
import sys
import time
import traceback
import audited_trial_campaign_v1 as wrapper

job, api = wrapper.job, wrapper.api
DESIGN = job.DESIGN.with_name('local_regression_01.json')
RUN = job.PREFLIGHT.with_name('known_transition_01')
OUT = job.OUT/'known_transition_01'


def prepare():
    d=api.read(job.DESIGN);job.verify(d)
    w=api.read(job.WORK)
    api.require(job.utc()<job.policy.utc(w['agent_work_end_utc']),'authorized work clock')
    protocol={'stage':'Stage190 local repair regression','maximum_new_steps':20000,'serial_steps':10000,
              'split_steps':[2794,7206],'wall_seconds':1200,'trajectory_initial_state':'verified historical checkpoint for diagnostics only',
              'sources':job.source_map(),'inputs':{str(p):api.sha(p) for p in (job.DESIGN,job.WORK,Path(d['diagnostic_seed']))},
              'production_launched':False,'claim':'Local exact trace/state/restart and independent audit. Not a full observation; historical failures stay failed.'}
    protocol['binding']=api.digest(protocol);api.write(DESIGN,protocol)
    print('FROZEN_LOCAL',api.sha(DESIGN),flush=True)


def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'local binding')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs']);job.verify(api.read(job.DESIGN))


def run():
    p=api.read(DESIGN);verify(p);d=api.read(job.DESIGN)
    api.require(job.utc()<job.policy.utc(api.read(job.WORK)['agent_work_end_utc'])-job.timedelta(seconds=1300),'local wall reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    deadline=min(job.utc()+job.timedelta(seconds=p['wall_seconds']),job.policy.utc(d['agent_work_end_utc'])).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':deadline,
                                'protocol_sha256':api.sha(DESIGN),'maximum_new_steps':20000})
    total=0;reports=[];started=time.perf_counter()
    try:
        job.parent.b.old.parent.configure();saved=api.read(d['diagnostic_seed'])
        case=next(c for c in d['cases'] if c['id']==saved['case'])
        cp=job.parent.model.checkpoint(case['spec'],job.binding(d,case),saved['checkpoint'],True)
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            _,data,meta=api.fields.load(2,1.,6)
            geo=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            def call(name,before,cap,prefix=None):
                nonlocal total
                api.require(total+cap<=p['maximum_new_steps'],'local new-step ceiling')
                path=RUN/(name+'.json.xz')
                rec,next_prefix,seal,elapsed=job.execute_segment(d,case,copy.deepcopy(before),path,cap,prefix,deadline)
                total+=len(rec['rows'])
                decoded,_=job.codec.read_record(path,api.sha(job.DESIGN),prefix)
                audit=job.kernel.evaluate(decoded,case['spec'],job.binding(d,case),before,geo,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                api.require(len(rec['rows'])==cap and rec['result']['status']=='paused_checkpoint','exact bounded interval')
                report={'path':str(path),'steps':len(rec['rows']),'audit':audit,'transaction_s':elapsed,'compute_s':rec['compute_call_wall_s'],'bytes':path.stat().st_size}
                job.commit(path.with_suffix('.audit.json'),report);reports.append(report)
                print('LOCAL_VERIFIED',name,total,flush=True)
                return rec,next_prefix
            serial,_=call('serial',cp,10000)
            api.require(serial['rows']==saved['oracle_rows'] and serial['result']['checkpoint']['state']==saved['oracle_state'],'exact historical trace/full-state identity')
            first,prefix=call('split_first',cp,2794)
            last,_=call('split_last',first['result']['checkpoint'],7206,prefix)
            api.require(serial['rows']==first['rows']+last['rows'] and serial['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact restart through original failure event')
        verify(p)
        result={'passed':True,'new_steps':total,'exact_archived_trace_and_state':True,'exact_restart':True,
                'all_original_physical_gates':True,'original_stage187_promoted':False,'cases':reports,
                'wall_seconds':time.perf_counter()-started,'protocol_sha256':api.sha(DESIGN),'design_sha256':api.sha(job.DESIGN),
                'artifacts':{str(f):api.sha(f) for f in RUN.rglob('*') if f.is_file()},'claim':p['claim']}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('LOCAL_REGRESSION_PASS',total,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'saved_new_steps':total,'protocol_sha256':api.sha(DESIGN)})
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare or run')
