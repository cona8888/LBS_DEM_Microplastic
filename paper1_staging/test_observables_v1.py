"""Hand-calculated nonuniform-clock and censoring controls; zero integration."""
import copy,math
from derive_observables_v1 import Measurements


def run():
    checks=[]
    spec=dict(initial_state=dict(position_m=[0.,0.,0.],orientation=[1.,0.,0.]),
        horizon_s=1.,config=dict(trap=dict(dwell_time_s=.5)))
    obs=dict(status='present_at_horizon',stop_s=1.,first_dwell_s=None)
    queries=[dict(kind='test',time_s=t) for t in (.125,.25,.5,.75,1.)]
    def row(t,contact,elapsed=0.,persistent=False):
        return dict(time_s=t,position_m=[t,0.,-2*t],orientation=[1.,0.,0.],
            active_contact_ids=[1,2] if contact else [],supported_bearing_ids=[1] if contact else [],
            dwell=dict(elapsed_s=elapsed,persistent_contact_observed=persistent))
    coarse=Measurements(spec,'rigid_prolate_ar4',obs,copy.deepcopy(queries))
    coarse.consume([row(.25,True)]);coarse.consume([row(1.,False)])
    a,samples=coarse.finish()
    assert a['active_contact_fraction']==a['supported_contact_fraction']==.25
    assert a['mean_active_contact_count']==.5 and a['mean_supported_contact_count']==.25
    assert a['maximum_active_episode_s']==a['maximum_supported_episode_s']==.25
    checks+=['unequal_interval_weighting','contact_count_time_integrals','episodes_across_blocks']
    half=next(q for q in samples if q['time_s']==.5)
    assert half['downstream_displacement_m']==.5 and half['vertical_displacement_m']==-1.
    assert half['active_contact_fraction']==.5 and math.isclose(half['path_length_m'],math.sqrt(5)*.5)
    assert math.isclose(a['path_length_m'],math.sqrt(5)) and a['mean_downstream_velocity_m_s']==1.
    assert a['fibre_director_angle_to_flow_rad']==0.
    checks+=['linear_pose_query','cumulative_contact_query','path_length_units','flow_director_angle']
    fine=Measurements(spec,'rigid_prolate_ar4',obs,copy.deepcopy(queries))
    fine.consume([row(t,True) for t in (.05,.1,.25)])
    fine.consume([row(.5,False),row(1.,False)])
    b,refined_samples=fine.finish()
    for key in ('active_contact_fraction','supported_contact_fraction','mean_active_contact_count',
                'mean_supported_contact_count','maximum_active_episode_s','path_length_m'):
        assert math.isclose(a[key],b[key],rel_tol=1e-14,abs_tol=1e-14),key
    checks.append('different_step_counts_same_physical_occupation')
    sphere=Measurements(spec,'equal_volume_sphere',obs,[]);sphere.consume([row(1.,False)])
    sphere_summary,_=sphere.finish()
    assert sphere_summary['fibre_director_angle_to_flow_rad'] is None
    checks.append('sphere_axis_inapplicable')
    exported=Measurements(spec,'rigid_prolate_ar4',dict(status='full_window_exit',stop_s=.6,first_dwell_s=None),
        [dict(kind='test',time_s=.75)])
    exported.consume([row(.2,False),row(.6,False)]);e,missing=exported.finish()
    assert e['export_time_s']==.6 and missing==[dict(kind='test',time_s=.75,available=False,reason='export_before_query')]
    checks.append('no_pose_or_contact_extrapolation_after_export')
    short=Measurements(spec,'rigid_prolate_ar4',dict(status='present_at_horizon',stop_s=.2,first_dwell_s=None),[])
    short.consume([row(.2,False)]);short_summary,_=short.finish()
    assert not short_summary['observed_duration_can_span_dwell_threshold']
    assert short_summary['first_persistent_contact_dwell_time_s'] is None
    checks.append('short_duration_dwell_eligibility')
    def reject(fn):
        try:fn()
        except RuntimeError:return
        raise AssertionError('Invalid raw clock or incomplete path admitted')
    invalid=Measurements(spec,'rigid_prolate_ar4',obs,[])
    reject(lambda:invalid.consume([row(.25,False),row(.25,False)]))
    incomplete=Measurements(spec,'rigid_prolate_ar4',obs,[]);incomplete.consume([row(.5,False)])
    reject(incomplete.finish)
    checks+=['nonmonotone_clock_rejected','incomplete_observation_rejected']
    print('PAPER1_OBSERVABLE_CONTROLS_PASSED',len(checks),'new_transport_steps=0',flush=True)


if __name__=='__main__':run()
