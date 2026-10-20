"""Bounded opt-in repair integration and cost qualification; no campaign launch.

Commands: prepare, run. Original cases, gaps and all physics are untouched.
This local development test is not empirical validation or a release estimate.
"""
from pathlib import Path
import copy, datetime as dt, os, shutil, sys, time, traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage169_staging'))
import local_regression_v2 as prior
job = prior.job
api, parent, repair, hot = job.api, job.parent, job.repair, job.hot
BASE = 'repaired_campaign_integration_20260923'
DESIGN = ROOT/'stage171_designs'/BASE/'design_01.json'
RUN = ROOT/'stage171_runs'/BASE/'preflight_01'
OUT = ROOT/'stage171_evaluations'/BASE/'evaluation_01'
AUDIT = OUT.parent/'independent_audit_01'
SELF = Path(__file__).resolve()
TOTAL = 0
START = None


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}), 'preflight binding')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    job.verify(api.read(job.DESIGN)); parent.verify(api.read(parent.DESIGN))


def prepare():
    old = api.read(parent.DESIGN); parent.verify(old)
    loc = api.read(job.DESIGN); job.verify(loc)
    assessment = job.unit.EVAL/'independent_audit_01'
    r, s = api.read(assessment/'results.json'), api.read(assessment/'completion.json')
    api.require(r['local_repair_verified'] and s['results_sha256']==api.sha(assessment/'results.json'), 'local repair qualified')
    api.verify_mapping(s['artifacts'])
    controls = []
    for name, predecessor, target in [
        ('sphere_healthy', 's2_i0_sphere_f0p03125/segment_00136.json.gz', 's2_i0_sphere_f0p03125/segment_00137.json.gz'),
        ('fibre_fine_healthy', 's2_i0_fibre_f0p03125/segment_00046.json.gz', 's2_i0_fibre_f0p03125/segment_00047.json.gz'),
        ('fibre_selected_healthy', 's2_i0_fibre_f0p0625/segment_00046.json.gz', 's2_i0_fibre_f0p0625/segment_00047.json.gz'),
    ]:
        before, saved = parent.storage.read_record(parent.RUN/predecessor, api.sha(parent.DESIGN)), parent.storage.read_record(parent.RUN/target, api.sha(parent.DESIGN))
        api.require(saved['input_checkpoint_sha256']==api.digest(before['result']['checkpoint']), 'archived control chain')
        api.require(saved['result']['rejected']==0 and not saved['result']['stage119_repair_calls'], 'healthy old control')
        controls.append({'id':name, 'source':str(parent.RUN/predecessor), 'target':str(parent.RUN/target), 'steps':1000})
    inputs = [parent.DESIGN, job.DESIGN, job.unit.DESIGN, assessment/'results.json', assessment/'completion.json',
              Path(loc['source_checkpoint']), Path(loc['source_checkpoint']).with_suffix('.seal.json')]
    for name in ['units_01','refined_units_01','refined_invariance_01']:
        inputs += [job.unit.EVAL/name/'results.json', job.unit.EVAL/name/'completion.json']
    for control in controls:
        for key in ['source','target']:
            p = Path(control[key]); inputs += [p, p.with_suffix('.seal.json')]
    d = {'stage':'Stage171', 'authorization':'User next approved revised target 25 September 2026 23:59 BST, subject to integration/cost checks.',
         'deadline_utc':'2026-09-25T22:59:00+00:00', 'simulation_cutoff_utc':'2026-09-25T18:59:00+00:00',
         'physics_changes':[], 'production_default_changed':False, 'observation_horizon_pv':.1,
         'purpose':'Test selected/fine/finer integration around repaired sphere event, unchanged healthy paths, exact restart and affordability.',
         'source_checkpoint':loc['source_checkpoint'], 'old_source_design_sha256':api.sha(parent.DESIGN),
         'failure_time_s':loc['horizon_s']-1e-4, 'local_horizon_s':loc['horizon_s']+4e-4,
         'factors_relative_to_old_fine':[2.,1.,.5], 'limits':loc['limits'], 'controls':controls,
         'budget':{'wall_s':900., 'maximum_new_steps':25000, 'step_cap':500, 'maximum_calls_per_level':40,
                   'threads':1, 'workers':1, 'minimum_free_disk_bytes':20*1024**3, 'runtime_margin':1.3},
         'restart_lengths':[100,37,63],
         'stop':'Any rejected trial, numerical/lineage/identity failure, wall/step budget or unaffordable cost blocks campaign promotion. No retuning or restart.',
         'claim':'Conditional integration qualification only. No population release, full-path accuracy, empirical validation or healthy-prefix migration authority.',
         'inputs':{str(p):api.sha(p) for p in inputs}, 'sources':parent.source_map()}
    d['binding']=api.digest(d); DESIGN.parent.mkdir(parents=True,exist_ok=True); api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def setup(d,factor):
    source=parent.storage.read_record(Path(d['source_checkpoint']),d['old_source_design_sha256'])
    spec=copy.deepcopy(source['spec']); spec['horizon_s']=d['local_horizon_s']
    spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    for key in api.DT_CONTROLS: spec['config']['numerics'][key]*=factor
    binding=api.digest([d['binding'],'sphere',factor])
    cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
    return spec,binding,cp


def check(rec,before,binding):
    job.check(rec,before,binding)
    api.require(rec['effective_binding']==parent.model.binding_for(binding,True), 'effective binding')
    api.require(rec['result']['time_s']<=rec['spec']['horizon_s'], 'declared clock horizon')
    api.require(all(x['reduced_accepted'] for x in rec['repairs']), 'new fallback accepted without old recovery')
    for c in rec['result']['stage119_repair_calls']:
        h=c['health']; f=np.asarray(h['reactions']); mu=rec['spec']['config']['friction_coefficient']
        api.require(np.isfinite(f).all() and np.all(f[::3]>=0), 'compressive finite reactions')
        api.require(all(np.linalg.norm(f[i+1:i+3])<=mu*f[i]+1e-12*max(np.linalg.norm(f),1e-30) for i in range(0,len(f),3)), 'original Coulomb cones')
        api.require(h['residual']<=1e-10 and h['force_residual']<=1e-8 and h['original_gaps_preserved'], 'unchanged final gates')


def execute(d,spec,binding,cp,path,cap):
    global TOTAL
    api.require(time.perf_counter()-START<d['budget']['wall_s'], 'preflight wall ceiling')
    api.require(TOTAL+cap<=d['budget']['maximum_new_steps'], 'preflight step ceiling')
    api.require(shutil.disk_usage(ROOT).free>=d['budget']['minimum_free_disk_bytes'], 'disk reserve')
    before=copy.deepcopy(cp); nr,nc,nf=len(repair.telemetry),len(parent.model.calls),len(parent.fix.telemetry)
    started=time.perf_counter()
    with hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),repair.scope(parent.engine.runtime,True):
        result,rows=parent.engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+cap)
    rec={'spec':spec,'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),
         'effective_binding':parent.model.binding_for(binding,True),'design_sha256':api.sha(DESIGN),'step_cap':cap,
         'repairs':copy.deepcopy(repair.telemetry[nr:]),'backend_calls':copy.deepcopy(parent.model.calls[nc:]),
         'certificates':copy.deepcopy(parent.fix.telemetry[nf:]),'compute_call_wall_s':time.perf_counter()-started}
    parent.storage.write_record(path,rec); TOTAL+=len(rows)
    api.require(api.digest(parent.storage.read_record(path,api.sha(DESIGN)))==api.digest(rec), 'lossless persisted evidence')
    check(rec,before,binding)
    print(path.relative_to(RUN),result['status'],'steps',len(rows),'t',result['time_s'],'repairs',len(rec['repairs']),flush=True)
    return rec


def comparisons(levels,d):
    reference=levels[-1]; start=reference['seed']['state']['t']; stop=d['local_horizon_s']
    U=reference['spec']['config']['target_mean_interstitial_velocity_m_s']; b=reference['spec']['config']['prolate_semiaxes_m'][1]
    result=[]
    for level in levels[:-1]:
        values={}
        for field,state_key,scale,label in [('position_m','x',b,'pose_b'),('orientation','p',1.,'axis')]:
            ts=[]; vs=[]
            for lev in [level,reference]:
                ts.append(np.array([start]+[row['time_s'] for row in lev['rows']]))
                vs.append(np.vstack([lev['seed']['state'][state_key],[row[field] for row in lev['rows']]]))
            grid=np.union1d(*ts)
            arrays=[np.column_stack([np.interp(grid,t,v[:,i]) for i in range(3)]) for t,v in zip(ts,vs)]
            values[label]=float(np.max(np.linalg.norm(arrays[0]-arrays[1],axis=1))/scale)
        values['endpoint_velocity_U']=float(np.linalg.norm(np.asarray(level['result']['velocity_generalized'])-reference['result']['velocity_generalized'])/U)
        values['mean_L1_velocity_U']=parent.b.q.diag.piecewise_l1(level['rows'],reference['rows'],start,stop,U)['mean_norm_over_scale']
        result.append({'factor':level['factor'],'metrics':values,'passed':all(v<=d['limits'][k] for k,v in values.items())})
    return result


def run():
    global START
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False);START=time.perf_counter()
    parent.b.old.parent.configure(); identities=[];levels=[];artifacts={}
    def bind(path):
        for p in [path,path.with_suffix('.seal.json')]:artifacts[str(p)]=api.sha(p)
    try:
        for control in d['controls']:
            source=parent.storage.read_record(Path(control['source']),d['old_source_design_sha256'])
            target=parent.storage.read_record(Path(control['target']),d['old_source_design_sha256'])
            spec=source['spec'];binding=api.digest([d['binding'],control['id']])
            cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
            path=RUN/(control['id']+'.json.gz');rec=execute(d,spec,binding,cp,path,control['steps']);bind(path)
            expected=target['rows'][:control['steps']]
            passed=rec['rows']==expected and not rec['repairs']
            api.require(passed and len(rec['rows'])==control['steps'], 'exact unchanged healthy trajectory')
            identities.append({'id':control['id'],'passed':passed,'steps':len(expected),'path':str(path)})
        for factor in d['factors_relative_to_old_fine']:
            spec,binding,cp=setup(d,factor);seed=copy.deepcopy(cp);rows=[];entries=[];post=[]
            folder=RUN/f'factor_{factor}';folder.mkdir()
            for i in range(d['budget']['maximum_calls_per_level']):
                before_t=cp['state']['t'];path=folder/f'segment_{i+1:03d}.json.gz'
                rec=execute(d,spec,binding,cp,path,d['budget']['step_cap']);bind(path)
                rows.extend(rec['rows']);entries.append({'path':str(path),'sha256':api.sha(path)})
                cp=rec['result']['checkpoint']
                if before_t>=d['failure_time_s']+1e-4 and len(rec['rows'])>=100:
                    post.append({'seconds_per_simulated_second':rec['compute_call_wall_s']/(cp['state']['t']-before_t),
                                 'path':str(path),'steps':len(rec['rows']),'repairs':len(rec['repairs'])})
                if rec['result']['status']=='present_at_horizon':break
            api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['local_horizon_s'], 'exact local observation completed')
            api.require(post, 'post-repair cost sampling')
            levels.append({'factor':factor,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result'],
                           'entries':entries,'post_repair_cost':post})
        # Restart at the repaired endpoint; no physical endpoint is absorbed.
        level=levels[1];spec=copy.deepcopy(level['spec']);spec['horizon_s']+=1e-3;spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
        binding=api.digest([d['binding'],'repair_restart']);cp=parent.model.checkpoint(spec,binding,level['result']['checkpoint'],True)
        folder=RUN/'restart';folder.mkdir()
        full=execute(d,spec,binding,cp,folder/'full.json.gz',100);bind(folder/'full.json.gz')
        first=execute(d,spec,binding,cp,folder/'first.json.gz',37);bind(folder/'first.json.gz')
        last=execute(d,spec,binding,first['result']['checkpoint'],folder/'last.json.gz',63);bind(folder/'last.json.gz')
        exact=full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state']
        api.require(exact and full['repairs'], 'exact restart through active fallback')
        metrics=comparisons(levels,d);passed=all(x['passed'] for x in metrics)
        result={'passed':passed,'identities':identities,'comparisons':metrics,'exact_restart':exact,'new_steps':TOTAL,
                'wall_s':time.perf_counter()-START,'design_sha256':api.sha(DESIGN),'artifacts':artifacts,
                'levels':[{'factor':x['factor'],'steps':len(x['rows']),'final':x['result'],'entries':x['entries'],'post_repair_cost':x['post_repair_cost']} for x in levels],
                'full_path_qualified':False,'campaign_launched':False}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
        print('PREFLIGHT',passed,'STEPS',TOTAL,'METRICS',metrics,flush=True)
    except Exception as error:
        api.write(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'saved_steps':TOTAL,'wall_s':time.perf_counter()-START})
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
