"""Read-only Paper1 measurements from complete, temporally qualified raw paths.

Contact weights follow accepted physical-clock intervals, not saved-row counts.
Pose queries use the original nodal linear convention; exports are not extended.
"""
from pathlib import Path
import argparse,csv,math,sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import compare_core_v1 as comparison
s=comparison.s;api=s.api
PROTOCOL=s.factory.CONTRACT.parent/'analysis_protocol_01.json'


class Measurements:
    def __init__(self,spec,shape,observation,queries):
        self.spec=spec;self.shape=shape;self.observation=observation
        initial=spec['initial_state'];self.initial=np.asarray(initial['position_m'],float)
        self.position=self.initial.copy();self.axis=np.asarray(initial['orientation'],float)
        self.time=0.;self.steps=0;self.parts=[];self.samples=[]
        self.queries=sorted(queries,key=lambda q:(q['time_s'],q['kind']))
        self.running=[None,None];self.maximum_episode=[0.,0.]
        self.maximum_monitor=0.;self.first_dwell=None
        api.require(all(math.isfinite(q['time_s']) and q['time_s']>0 for q in self.queries),'Positive finite queries')

    def totals(self):
        return np.asarray([math.fsum(float(p[k]) for p in self.parts) for k in range(6)])

    def pose_fields(self,position,axis):
        displacement=position-self.initial
        if self.shape=='rigid_prolate_ar4':
            norm=float(np.linalg.norm(axis));api.require(norm>0,'Nonzero interpolated director')
            director=(axis/norm).tolist()
            angle=math.atan2(float(np.linalg.norm(axis[1:])),abs(float(axis[0])))
        else:director=angle=None
        return dict(position_m=position.tolist(),downstream_displacement_m=float(displacement[0]),
            vertical_displacement_m=float(displacement[2]),net_displacement_m=float(np.linalg.norm(displacement)),
            fibre_director_unit_vector=director,fibre_director_angle_to_flow_rad=angle)

    @staticmethod
    def contact_fields(totals):
        elapsed=float(totals[0]);api.require(elapsed>0,'Positive observed interval duration')
        return dict(integrated_clock_duration_s=elapsed,active_contact_duration_s=float(totals[1]),
            supported_contact_duration_s=float(totals[2]),active_contact_fraction=float(totals[1]/elapsed),
            supported_contact_fraction=float(totals[2]/elapsed),mean_active_contact_count=float(totals[3]/elapsed),
            mean_supported_contact_count=float(totals[4]/elapsed),path_length_m=float(totals[5]))

    def consume(self,rows):
        api.require(bool(rows),'Nonempty accepted raw block')
        times=np.asarray([self.time]+[r['time_s'] for r in rows],float);dt=np.diff(times)
        api.require(np.isfinite(times).all() and np.all(dt>0),'Strict accepted physical clock')
        positions=np.vstack([self.position,[r['position_m'] for r in rows]])
        axes=np.vstack([self.axis,[r['orientation'] for r in rows]])
        api.require(np.isfinite(positions).all() and np.isfinite(axes).all(),'Finite original raw poses')
        counts=np.asarray([[len(r['active_contact_ids']),len(r['supported_bearing_ids'])] for r in rows])
        distance=np.linalg.norm(np.diff(positions,axis=0),axis=1)
        integrals=np.column_stack((dt,dt*(counts[:,0]>0),dt*(counts[:,1]>0),
            dt*counts[:,0],dt*counts[:,1],distance))
        prefix=np.vstack([np.zeros(6),np.cumsum(integrals,axis=0)]);before=self.totals()
        while self.queries and self.queries[0]['time_s']<=times[-1]:
            query=self.queries.pop(0);t=query['time_s']
            api.require(t>times[0],'Query consumed exactly once, without extrapolation')
            index=int(np.searchsorted(times,t,side='left'))-1
            fraction=(t-times[index])/dt[index]
            position=positions[index]+fraction*(positions[index+1]-positions[index])
            axis=axes[index]+fraction*(axes[index+1]-axes[index])
            totals=before+prefix[index]+fraction*integrals[index]
            self.samples.append({**query,'available':True,**self.pose_fields(position,axis),**self.contact_fields(totals)})
        for index,row in enumerate(rows):
            for mode in range(2):
                if counts[index,mode]:
                    if self.running[mode] is None:self.running[mode]=float(times[index])
                    self.maximum_episode[mode]=max(self.maximum_episode[mode],float(times[index+1])-self.running[mode])
                else:self.running[mode]=None
            self.maximum_monitor=max(self.maximum_monitor,float(row['dwell']['elapsed_s']))
            if self.first_dwell is None and row['dwell']['persistent_contact_observed']:self.first_dwell=row['time_s']
        self.parts.append(np.asarray([math.fsum(float(v) for v in integrals[:,k]) for k in range(6)]))
        self.time=float(times[-1]);self.position=positions[-1].copy();self.axis=axes[-1].copy();self.steps+=len(rows)

    def finish(self):
        obs=self.observation
        api.require(self.steps>0 and self.time==obs['stop_s'] and self.first_dwell==obs['first_dwell_s'],
            'Entire observed raw clock and original dwell event')
        exported=obs['status']=='full_window_exit'
        for query in self.queries:
            self.samples.append({**query,'available':False,
                'reason':'export_before_query' if exported else 'outside_observed_horizon'})
        threshold=self.spec['config']['trap']['dwell_time_s']
        result=dict(status=obs['status'],observed_stop_s=self.time,horizon_s=self.spec['horizon_s'],
            observed_steps=self.steps,whole_body_control_volume_export=exported,
            export_time_s=self.time if exported else None,first_persistent_contact_dwell_time_s=self.first_dwell,
            original_dwell_threshold_s=threshold,observed_duration_can_span_dwell_threshold=self.time>=threshold,
            maximum_original_monitor_elapsed_s=self.maximum_monitor,maximum_active_episode_s=self.maximum_episode[0],
            maximum_supported_episode_s=self.maximum_episode[1],
            mean_downstream_velocity_m_s=float((self.position[0]-self.initial[0])/self.time),
            **self.pose_fields(self.position,self.axis),**self.contact_fields(self.totals()))
        return result,sorted(self.samples,key=lambda q:(q['kind'],q['time_s']))


def queries_for(spec,decision):
    return ([dict(kind='common_pv',target_pv=pv,time_s=spec['horizon_s']*(pv/decision['selected_pv']))
             for pv in decision['common_pv_queries']]+
            [dict(kind='common_physical_time',time_s=t) for t in decision['common_physical_time_queries_s']])


def derive(root,qualified,decision):
    root=Path(root).resolve();plan_path=s.ROOT/'paper1_designs'/root.name/'design_01.json'
    physical=plan_path.with_name('physical_cases_01.json');plan=s.read(plan_path);case=s.read(physical)['cases'][0]
    final=s.fields.sealed(root/'final_disposition_01/results.json');retired=s.fields.sealed(root/'retirement_01/results.json')
    api.require(plan['logical_core_id']==qualified['logical_core_id'] and final['passed'] and retired['passed']
        and final['native_complete'] and retired['all_exact_owned_identities_retired']
        and final['known_unaccepted_saved_steps']==final['unknown_reserved_steps_upper_bound']==0,'Complete qualified case')
    pins={str(path.resolve()):s.sha(path) for path in (plan_path,physical,root/'final_disposition_01/results.json',
        root/'retirement_01/results.json')}
    api.require(all(qualified['evidence_files'].get(path)==digest for path,digest in pins.items()),'Exact comparison lineage')
    for key in ('artifacts','closed_logs'):api.verify_mapping(retired[key])
    api.verify_mapping(plan['source_files']);api.verify_mapping(plan['physical_inputs'])
    observation=qualified['observations'][0 if case['factor']==.125 else 1]
    api.require(case['factor'] in (.125,.0625) and observation['complete_observation'],'Original coarse/fine roles')
    expected_id=qualified['core_case'] if case['factor']==.125 else qualified['reference_case']
    api.require(case['id']==expected_id,'Exact compared variant')
    for identity in retired['identities']:
        api.require(s.sha(identity['path'])==identity['sha256'] and s.identity(s.read(identity['path']))['retired'],
                    'Fresh exact retired identities')
    labels=final['production_labels']
    api.require(labels==[f'production_{i:05d}' for i in range(1,len(labels)+1)]
        and sorted(p.name for p in (root/'records').glob('production_*'))==labels,'Complete production inventory')
    measurements=Measurements(case['spec'],case['shape'],observation,queries_for(case['spec'],decision))
    codec=comparison.shared.archives.build(s.q.job.codec,preset=9);prefix=before=None
    for label in labels:
        folder=root/'records'/label;raw=folder/'call.json.xz'
        rec,prefix=codec.read_record(raw,s.sha(physical),prefix)
        api.require(rec['spec']==case['spec'] and rec['input_checkpoint_sha256']==api.digest(before),
                    'Exact full raw ancestry for derived measurements')
        measurements.consume(rec['rows']);before=rec['result']['checkpoint']
        api.require(before['state']['steps']==measurements.steps and before['state']['t']==measurements.time,
                    'Every physical step and accepted clock represented')
    api.require(measurements.steps==final['accepted_physical_steps'] and api.digest(before)==final['full_checkpoint_sha256'],
                'Entire terminal state, never a prefix')
    summary,samples=measurements.finish()
    return dict(logical_core_id=plan['logical_core_id'],case_id=case['id'],factor=case['factor'],shape=case['shape'],
        placement_id=case['spec']['sample_id'],nominal_flow_level=case['spec']['flow_factor'],
        summary=summary,queries=samples,evidence_files=pins)


def run(comparison_path,coarse_root,fine_root,destination):
    s.environment();destination=Path(destination).resolve()
    api.require(s.ROOT/'paper1_evaluations' in destination.parents and not destination.exists(),'Fresh derived evidence destination')
    protocol=s.read(PROTOCOL);decision=s.fields.sealed(s.factory.EXPOSURE)
    api.require(protocol['schema']=='paper1.analysis.v1' and protocol['flow_direction']==[1.,0.,0.]
        and protocol['original_accuracy_gate_changes']==protocol['original_physics_changes']==[],
        'Frozen interpretation protocol; original gates and physics unchanged')
    qualified=s.fields.sealed(comparison_path)
    api.require(qualified['passed'] and qualified['whole_start_to_terminal_paths'] and qualified['full_path_gates']['passed']
        and qualified['original_gate_values']==s.q.job.policy.GATES,'Original whole-path temporal admission')
    for key in ('source_files','evidence_files','path_artifacts'):api.verify_mapping(qualified[key])
    variants=[derive(coarse_root,qualified,decision),derive(fine_root,qualified,decision)]
    api.require([v['factor'] for v in variants]==[.125,.0625],'Declared coarse then fine ordering')
    destination.mkdir(parents=True,exist_ok=False)
    table=destination/'summary.csv'
    keys=['case_id','factor','shape','placement_id','nominal_flow_level']
    scalar_keys=[k for k in variants[0]['summary'] if k not in ('position_m','fibre_director_unit_vector')]
    with table.open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=keys+scalar_keys);writer.writeheader()
        for variant in variants:writer.writerow({**{k:variant[k] for k in keys},**{k:variant['summary'][k] for k in scalar_keys}})
    differences={k:abs(variants[0]['summary'][k]-variants[1]['summary'][k]) for k in protocol['features']
        if variants[0]['summary'][k] is not None and variants[1]['summary'][k] is not None}
    source=Path(__file__).resolve()
    s.seal(destination,dict(passed=True,new_transport_steps=0,logical_core_id=qualified['logical_core_id'],
        scope='Derived labelled measurements; no shape/flow inference or study completion',
        variants=variants,absolute_coarse_fine_feature_changes=differences,
        source_files={str(source):s.sha(source),**qualified['source_files']},
        inputs={str(Path(comparison_path).resolve()):s.sha(comparison_path),str(PROTOCOL):s.sha(PROTOCOL),
                str(s.factory.EXPOSURE):s.sha(s.factory.EXPOSURE)},artifacts={str(table):s.sha(table)},
        reproduce_command=[sys.executable,'-B',str(source),*sys.argv[1:]],utc=s.utc()))
    print('PAPER1_OBSERVABLES_DERIVED',qualified['logical_core_id'],s.sha(destination/'results.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('comparison','coarse_root','fine_root','destination'):parser.add_argument(name,type=Path)
    args=parser.parse_args();run(args.comparison,args.coarse_root,args.fine_root,args.destination)
