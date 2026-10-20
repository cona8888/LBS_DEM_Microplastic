"""Version 2 verification; preserve version 1's failed refinement evidence."""
import copy,sys,time
import verify_reduced_repair_v1 as base
import reduced_contact_repair_v2 as revised
OLD_DESIGN=base.DESIGN
OLD_EVAL=base.EVAL
OLD_RUN=base.RUN
base.repair=revised
base.DESIGN=base.DESIGN.with_name('design_02.json')
base.EVAL=base.EVAL/'v2'
base.RUN=base.RUN.with_name('local_02')
api=base.api;parent=base.parent;c=base.c


def prepare():
    d=api.read(OLD_DESIGN);base.verify(d)
    failure=OLD_EVAL/'local_evaluation_01/failure.json'
    raw=OLD_RUN/'factor_0.5/segment_006.json.gz'
    d=copy.deepcopy(d);d.pop('binding')
    d['algorithm']='Failure-only cone-feasible force-nullspace selection for two/three sticking contacts, plus original-gap one-stick/two-slide scalar force-balance root. Original physical gates unchanged.'
    d['revision']='V1 fixed original trial but failed half-timestep; preserve that failure and add its 23 archived rejected poses as development tests.'
    d['tests'].append('23 additional version-1 half-step rejected poses')
    d['sources']=parent.source_map()
    for p in [OLD_DESIGN,failure,raw,raw.with_suffix('.seal.json'),OLD_EVAL/'refined_failure_capture_01/results.json',OLD_EVAL/'refined_failure_capture_01/completion.json']:
        d['inputs'][str(p)]=api.sha(p)
    d['binding']=api.digest(d);base.EVAL.mkdir(exist_ok=False);api.write(base.DESIGN,d)
    print('V2 FROZEN',api.sha(base.DESIGN),flush=True)


def units():
    base.units()
    api.require(api.read(base.EVAL/'units_01/results.json')['passed'],'version-2 original units')
    d=api.read(base.DESIGN);base.verify(d);out=base.EVAL/'refined_units_01';out.mkdir()
    raw=OLD_RUN/'factor_0.5/segment_006.json.gz'
    # The old local protocol hash remains the authority for this failed record.
    oldprotocol=base.ROOT/'stage169_designs'/base.BASE/'local_protocol_01.json'
    rec=parent.storage.read_record(raw,api.sha(oldprotocol));spec=rec['spec']
    field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=c.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    rows={row['time_s']:row for row in rec['rows']};reports=[]
    trials=rec['result']['rejected_trials'];api.require(len(trials)==23,'refined failure accounting')
    with base.hot.scope(),parent.fix.scope(),revised.scope(parent.engine.runtime,True):
        for i,trial in enumerate(trials):
            row=rows[trial['time_s']];state={'x':row['position_m'],'p':row['orientation'],'q':row['velocity_generalized'],'t':row['time_s'],'recovery':False}
            try:q,h=c.diag.replay(field,geometry,spec,state,trial['dt_s'])
            except RuntimeError as error:reports.append({'id':i,'passed':False,'error':str(error)});continue
            reports.append({'id':i,'passed':h['contact_residual']<=1e-10 and h['momentum_residual']<=1e-8,'health':h,'velocity':q})
    result={'passed':all(x['passed'] for x in reports),'probes':reports,'steps':0,'source_sha256':api.sha(__file__),'design_sha256':api.sha(base.DESIGN)}
    base.verify(d);api.write(out/'results.json',result,raw=True);api.write(out/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(out/'results.json')})
    print('V2 EXTRA PROBES',result['passed'],sum(r['passed'] for r in reports),'/',len(reports),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['units']:units()
    else:raise ValueError('prepare or units')
