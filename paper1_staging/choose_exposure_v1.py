"""Prospective resource selection, blind to shape contrasts/export outcomes.

Forecasts are admission planning, not a guarantee of late-horizon cost or an
accuracy pass. Original whole-path/event and physics gates remain mandatory.
"""
from pathlib import Path
import sys,math,shutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cost_screen_v1 as s
ROOT=s.ROOT;OUT=s.factory.CONTRACT.parent/'exposure_decision_01'


def run():
    assert not OUT.exists()
    contract=s.factory.contract();screen=s.fields.sealed(s.OUT/'final_disposition_01/results.json')
    retirement=s.fields.sealed(s.OUT/'retirement_01/results.json');assert retirement['passed'] and screen['passed']
    storage=ROOT/'paper1_runs/storage_qualification_20261013'
    raw=s.fields.sealed(storage/'results.json');docs=s.fields.sealed(storage/'documents_01/qualification_01/results.json')
    assert raw['passed'] and docs['passed'] and raw['new_transport_steps']==docs['new_transport_steps']==0
    for gate in [raw,docs]:s.api.verify_mapping(gate['artifacts']);s.api.verify_mapping(gate['source_files'])
    s.api.verify_mapping(raw['inputs']);s.api.verify_mapping(docs['original_source_inputs'])
    profiles={}
    for item in screen['completed_domain_prefixes']:
        shape='sphere' if 'sphere' in item['core_id'] else 'fibre'
        profiles.setdefault(shape,[]).append(item['advanced_physical_seconds']/item['saved_steps'])
    dt={shape:min(values) for shape,values in profiles.items()}
    # Verified compression samples: all six prospective sphere prefixes plus
    # a sealed mature sphere; mature difficult fibre uses the larger raw rate.
    # Fixed margins also cover receipts/seals/launch records; traces stay NPY.
    per_step=dict(sphere=245.48046875+104+25+10,
                  fibre=3878256/4124+104+25+10)
    initial_bytes=sum(p.stat().st_size for dirname in ['paper1_runs','paper1_designs']
                      for p in (ROOT/dirname).rglob('*') if p.is_file())
    reserve=1.30;rows=[];means={}
    for flow in (.5,1.,2.):
        field,data,metadata=s.fields.load(2,flow,6);means[flow]=metadata
        del field,data
    for pv in contract['exposure_selection']['candidate_pv']:
        variants=[]
        for case in contract['cases']:
            shape='sphere' if case['shape']=='equal_volume_sphere' else 'fibre'
            horizon=pv/means[case['nominal_flow_level']]['pv_per_second']
            for factor in (.125,.0625):
                steps=math.ceil(reserve*horizon/dt[shape]*(.125/factor))
                variants.append(dict(core_id=case['id'],shape=shape,factor=factor,steps=steps))
        # Third-level checks: both shape classes, including the difficult
        # fibre placement. Grid controls are paired at the same middle flow.
        targeted=[('p1_i0_equal_volume_sphere_u1p0','sphere'),('p1_i124_rigid_prolate_ar4_u1p0','fibre')]
        for ident,shape in targeted:
            horizon=pv/means[1.]['pv_per_second']
            for role,ratio in [('third_refinement',4),('spatial_control',1)]:
                variants.append(dict(core_id=ident,shape=shape,role=role,steps=math.ceil(reserve*horizon/dt[shape]*ratio)))
        grouped={case['id']:sum(v['steps'] for v in variants if v['core_id']==case['id']) for case in contract['cases']}
        calls={ident:sum(math.ceil(v['steps']/4000) for v in variants if v['core_id']==ident) for ident in grouped}
        # Future protocol must store full raw/history plus compressed COMPLETE
        # audit output, retaining one standalone terminal FULL checkpoint per
        # variant. Repeating full checkpoints per segment is not affordable.
        data_bytes=initial_bytes+sum(v['steps']*per_step[v['shape']] for v in variants)+len(variants)*600000+256*1024**2
        elapsed=sum(math.ceil(v['steps']/4000)*75 for v in variants)+6*3600
        flags=dict(retained_data=data_bytes<=18*1024**3,elapsed=elapsed<=300*3600,
                   per_case_steps=max(grouped.values())<=5000000,per_case_calls=max(calls.values())<=1500,
                   free_reserve=shutil.disk_usage(ROOT).free-(data_bytes-initial_bytes)>20*1024**3)
        rows.append(dict(pv=pv,planning_admissible=all(flags.values()),checks=flags,
            forecast_retained_gib=data_bytes/1024**3,forecast_elapsed_hours=elapsed/3600,
            maximum_case_steps=max(grouped.values()),maximum_case_calls=max(calls.values()),variants=variants))
    candidates=[r for r in rows if r['planning_admissible']]
    assert candidates,'No common candidate fits declared conservative planning bounds'
    selected=max(candidates,key=lambda r:r['pv']);pv=selected['pv']
    shortest=min(pv/meta['pv_per_second'] for meta in means.values())
    sources={str(Path(__file__).resolve()):s.sha(__file__)}
    inputs={str(p):s.sha(p) for p in [s.factory.CONTRACT,s.OUT/'final_disposition_01/results.json',
        s.OUT/'retirement_01/results.json',storage/'results.json',storage/'documents_01/qualification_01/results.json']}
    s.seal(OUT,dict(passed=True,scope='Prospective resource/exposure decision; no full-horizon accuracy promotion',
        contract_sha256=s.factory.CONTRACT_SHA,selected_pv=pv,frozen_before_core_comparisons=True,
        accuracy_gates_remain_required=True,core_comparisons_completed=0,outcomes_used_for_selection=False,
        candidate_forecasts=rows,observed_shape_dt_s=dt,per_step_retained_byte_forecast=per_step,
        step_uncertainty_multiplier=reserve,complete_transaction_seconds_per_4000_forecast=75,
        required_storage_protocol='Qualified numeric raw archives; original complete audit results compressed losslessly; native NPY traces; no repeated per-segment FULL checkpoint copies; complete contiguous raw/history chain and final standalone FULL checkpoint retained.',
        planning_estimates_not_guarantees=True,stop_on_any_original_gate_or_resource_failure=True,
        common_pv_queries=[pv*f for f in (.25,.5,.75,1.)],common_physical_time_queries_s=[shortest*f for f in (.25,.5,.75,1.)],
        dwell_threshold_s=.5,dwell_interpretation='Do not compare absent persistent-dwell flags as trapping rates when exposure is shorter than0.5s; report eligibility/censoring and contact occupancy/history separately.',
        exposure_horizons_s={str(flow):pv/meta['pv_per_second'] for flow,meta in means.items()},
        source_files=sources,inputs=inputs,utc=s.utc()))
    print('EXPOSURE_FROZEN',pv,s.sha(OUT/'results.json'))
    for r in rows:print(r['pv'],r['planning_admissible'],r['forecast_retained_gib'],r['forecast_elapsed_hours'],r['checks'])


if __name__=='__main__':run()
