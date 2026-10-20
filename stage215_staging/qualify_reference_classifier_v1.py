"""Zero-step reference classifier/binding controls, before any new trajectory."""
from pathlib import Path
import copy,math
import bounded_policy_references_v1 as base
api,job=base.api,base.job
OUT=base.OUT/'prelaunch_qualification_01'

def run():
    w,d=base.prerequisites();base.no_worker()
    api.require(not OUT.exists() and not list(base.RUN.glob('*/launch.json')),'exclusive zero-step launch qualification')
    raw=base.prior.job.PREFLIGHT/'probes/s2_i0_sphere_f0p03125_contact.json.xz'
    record,_=job.codec.read_record(raw,api.sha(base.prior.job.DESIGN))
    contexts=record['normal_gap_operand_policy']['prepare_calls'][0]['metadata']
    controls=[];matches=[]
    for item in contexts:
        c=item['context'];rawgap=c['raw_gap_m'];band=base.prior.local.auditor.band(c['x'],c['c'],c['a'],c['r'])
        values=[rawgap,0.,-0.,band,-band,math.nextafter(band,math.inf),math.nextafter(-band,-math.inf)]
        for g in values:
            args=(c['x'],c['c'],c['a'],c['b'],c['r'],g)
            actual,meta=base.reference.classify(*args);old,oldmeta=base.prior.local.policy_scope.policy.classify(*args)
            api.require(float(actual).hex()==float(old).hex() and meta==oldmeta,'all fixed scalar/metadata policy results exact')
            expected=0. if abs(g)<=band else g
            api.require(float(actual).hex()==float(expected).hex(),'signed/outside boundary independently specified result')
            matches.append(dict(grain=c['grain_id'],raw_gap_hex=float(g).hex(),effective_gap_hex=float(actual).hex(),metadata_sha256=api.digest(meta)))
    c=contexts[0]['context']
    with base.reference.forbid_producer():
        value,_=base.reference.classify(c['x'],c['c'],c['a'],c['b'],c['r'],c['raw_gap_m'])
        api.require(value==0.,'independent reference active while producer forbidden')
        try:base.prior.local.policy_scope.policy.classify(c['x'],c['c'],c['a'],c['b'],c['r'],c['raw_gap_m'])
        except AssertionError:controls.append('producer sentinel proven active')
        else:raise AssertionError('producer remained callable')
    changes=[('physics',lambda x:x['cases'][0]['spec']['config'].update(friction_coefficient=0.)),
        ('policy_contract',lambda x:x.update(numerical_policy_contract_sha256='0'*64)),
        ('source',lambda x:x['sources'].update({str(base.SELF):'0'*64})),
        ('production',lambda x:x.update(production_authorized=True)),
        ('classifier_binding',lambda x:x['independent_reference_bindings'].update(producer_classifier_used=True))]
    for label,change in changes:
        bad=copy.deepcopy(d);change(bad);bad['binding']=api.digest({k:v for k,v in bad.items() if k!='binding'})
        try:base.verify(bad)
        except Exception:controls.append(label)
        else:raise AssertionError('corrupt reference design accepted '+label)
    inputs={str(p):api.sha(p) for p in (Path(__file__),base.SELF,Path(base.reference.__file__),base.DESIGN,base.WORK,raw,raw.with_suffix('.seal.json'))}
    result=dict(passed=True,new_trajectory_steps=0,fixed_policy_boundary_cases=len(matches),cases=matches,negative_controls_rejected=controls,
        independent_scope_bound=base.bindings(),design_sha256=api.sha(base.DESIGN),inputs=inputs,production_authorized=False)
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('REFERENCE_PRELAUNCH_PASS',len(matches),len(controls),api.sha(OUT/'results.json'),flush=True)

if __name__=='__main__':run()
