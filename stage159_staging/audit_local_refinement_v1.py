"""Re-read immutable chains and independently integrate interval errors/impulses."""
import numpy as np
import local_impact_refinement_v1 as v


def l1_merge(a,b,start,stop,U):
    i=j=0;t=start;total=0.
    while t<stop:
        right=min(a[i]['time_s'],b[j]['time_s'])
        total+=(right-t)*np.linalg.norm(np.array(a[i]['velocity_generalized'])-b[j]['velocity_generalized'])/U
        t=right
        if a[i]['time_s']==t:i+=1
        if b[j]['time_s']==t:j+=1
    return float(total/(stop-start))


def main():
    api=v.api;d=api.read(v.DESIGN);v.verify(d);r=api.read(v.OUT/'results.json')
    api.require(api.read(v.OUT/'completion.json')['results_sha256']==api.sha(v.OUT/'results.json'),'completion seal')
    api.verify_mapping(r['artifacts']);api.require(not (v.RUN/'failure.json').exists(),'no runtime or primary failure')
    v.old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=v.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    reports=[]
    for wi,w in enumerate(d['windows']):
        folder=v.RUN/w['id'];spec,binding,cp=v.seed_setup(d,wi);seed=v.read(folder/'seed.json')
        v.check(seed,cp,spec,binding)
        expected=api.read(v.source_path(w,w['next_segment']))['rows'][:d['entries'][wi]['steps']]
        api.require(seed['rows']==expected,'exact entry prefix')
        spec,binding,cp=v.setup(d,wi,v.FACTORS[-1],'preflight')
        full,first,last=[v.read(folder/f'preflight_{x}.json') for x in ['full','first','last']]
        v.check(full,cp,spec,binding);v.check(first,cp,spec,binding);v.check(last,first['result']['checkpoint'],spec,binding)
        api.require(len(full['rows'])==100 and len(first['rows'])==37 and len(last['rows'])==63,'restart counts')
        api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact restart')
        recs=[v.joined(d,wi,f) for f in v.FACTORS];imp=api.read(v.OUT/f"{w['id']}_impulses.json")
        repeat=v.impulses(d,wi,recs,field,geometry)
        api.require(repeat==imp,'independent repeated impulse replay')
        totals=[]
        for level in imp['levels']:
            total=np.array([sum(s['impulse_generalized'][k]*s['overlap_s']/s['dt_s'] for s in level['samples']) for k in range(6)])
            api.require(np.allclose(total,level['total_impulse'],rtol=1e-13,atol=1e-30),'independent component impulse sum')
            totals.append(total)
        errors=[float(np.linalg.norm(np.linalg.solve(np.array(imp['mass_at_entry']),x-totals[-1]))/imp['U']) for x in totals[:-1]]
        api.require(np.allclose(errors,imp['to_finest'],rtol=1e-10,atol=1e-13),'independent impulse metric')
        report=v.summary(d,wi,recs,imp)
        api.require(report==r['windows'][wi] and report['passed'],'scientific recomputation')
        independent=[l1_merge(x['rows'],recs[-1]['rows'],seed['result']['time_s'],w['horizon_s'],imp['U']) for x in recs[:-1]]
        api.require(np.allclose(independent,report['whole_L1_to_finest'],rtol=1e-12,atol=1e-14),'independent merge L1')
        reports.append({'id':w['id'],'all_gates_passed':True,'independent_L1':independent,'independent_impulse_errors':errors})
        print('AUDITED',w['id'],flush=True)
    v.verify(d)
    out=v.OUT.parent/'independent_audit_01';out.mkdir(exist_ok=False)
    result={'audit_integrity_passed':True,'scientific_gates_passed':True,'windows':reports,
            'evaluation_sha256':api.sha(v.OUT/'results.json'),'auditor_sha256':api.sha(__file__),
            'production_promotion':False,'full_path_accuracy':False}
    api.write(out/'results.json',result);api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'passed':True})
    print('STAGE159 INDEPENDENT AUDIT PASS',flush=True)


if __name__=='__main__':main()
