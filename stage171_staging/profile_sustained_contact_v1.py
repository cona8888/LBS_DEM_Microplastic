"""Frozen-pose cost diagnostic only; no trajectory step or physics change."""
from pathlib import Path
import cProfile, pstats, time
from collections import Counter
import numpy as np
import repaired_campaign_preflight_v1 as p

api,parent=p.api,p.parent
OUT=p.OUT.parent/'fixed_pose_profile_01'


def main():
    d=api.read(p.DESIGN);p.verify(d)
    path=p.RUN/'factor_1.0/segment_007.json.gz';next_path=path.with_name('segment_008.json.gz')
    record=parent.storage.read_record(path,api.sha(p.DESIGN));following=parent.storage.read_record(next_path,api.sha(p.DESIGN))
    api.require(following['input_checkpoint_sha256']==api.digest(record['result']['checkpoint']),'profile input chain')
    spec=record['spec'];row=record['rows'][-1];expected=following['rows'][0]
    state={'x':row['position_m'],'p':row['orientation'],'q':row['velocity_generalized'],'t':row['time_s'],'recovery':False}
    capture=p.job.unit.c
    parent.b.old.parent.configure()
    field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=capture.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    profile=cProfile.Profile();outcomes=[];timings=[]
    with p.hot.scope(),parent.fix.scope(),p.repair.scope(parent.engine.runtime,True):
        q,h=capture.diag.replay(field,geometry,spec,state,expected['dt_s'])
        api.require(q.tolist()==expected['velocity_generalized'],'exact archived next velocity')
        for _ in range(5):
            started=time.perf_counter();profile.enable()
            q,h=capture.diag.replay(field,geometry,spec,state,expected['dt_s'])
            profile.disable();timings.append(time.perf_counter()-started)
            outcomes.append(q.tolist()==expected['velocity_generalized'] and h['contact_residual']<=1e-10 and h['momentum_residual']<=1e-8)
    rows=[]
    for (file,line,name),(primitive,total,self_s,cumulative,callers) in pstats.Stats(profile).stats.items():
        if 'MATDEM_MICROPLASTIC' in file or name in ['_root_leastsq','_root_hybr','leastsq','root','least_squares']:
            rows.append({'file':file,'line':line,'function':name,'primitive_calls':primitive,'total_calls':total,
                         'self_s':self_s,'cumulative_s':cumulative})
    rows.sort(key=lambda x:x['cumulative_s'],reverse=True)
    states=Counter(tuple(x['position_m']+x['orientation']+x['velocity_generalized']+[x['dt_s']]) for x in record['rows'])
    result={'passed':all(outcomes),'probe_count':6,'profiled_repeats':5,'new_trajectory_steps':0,
            'exact_archived_velocity':True,'timed_probe_s':timings,'profile_top_30':rows[:30],
            'trace_segment_steps':len(record['rows']),'trace_segment_compute_s':record['compute_call_wall_s'],
            'trace_segment_repaired_solve_s':sum(x['wall_s'] for x in record['repairs']),
            'trace_segment_repaired_solve_calls':len(record['repairs']),
            'unique_full_kinematic_states':len(states),'maximum_exact_state_repetition':max(states.values()),
            'claim':'One frozen sustained-contact state and one archived segment; profiling overhead is not a campaign runtime estimate.',
            'source_sha256':api.sha(__file__),'input_hashes':{str(x):api.sha(x) for x in [p.DESIGN,path,path.with_suffix('.seal.json'),next_path,next_path.with_suffix('.seal.json')]}}
    p.verify(d);OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',result)
    api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('PROFILE',result['passed'],'NEW_STEPS',0,'TOP',rows[:10],flush=True)


if __name__=='__main__':main()
