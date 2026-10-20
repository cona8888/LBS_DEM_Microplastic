"""Preserve the first local-refinement failure's algebraic systems only."""
import copy,time
import numpy as np
import local_regression_v1 as local
c=local.unit.c;api=local.api;parent=local.parent;hot=local.hot
OUT=local.unit.EVAL/'refined_failure_capture_01'


def main():
    d=api.read(local.DESIGN);local.verify(d)
    path=local.RUN/'factor_0.5/segment_006.json.gz';rec=parent.storage.read_record(path,api.sha(local.DESIGN))
    failure=rec['result']['rejected_trials'][0];row=next(r for r in rec['rows'] if r['time_s']==failure['time_s'])
    state={'x':row['position_m'],'p':row['orientation'],'q':row['velocity_generalized'],'t':row['time_s'],'recovery':False}
    spec=rec['spec'];parent.b.old.parent.configure();field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=c.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    OUT.mkdir(exist_ok=False);api.write(OUT/'protocol.json',{'source_sha256':api.sha(__file__),'input_sha256':api.sha(path),'state':state,'trial':failure,'steps':0})
    records=[]
    with hot.scope(),parent.fix.scope(),local.repair.scope(parent.engine.runtime,True):
        saved=hot.s50._finish;compiled=hot.PRIMARY.__globals__['_finish']
        def observe(*args,**kwargs):
            names=['vfree','mobility','jacobian','force','z','A','gaps','dt','friction','steps','iterations','solver','extra']
            p={k:copy.deepcopy(v) for k,v in zip(names,args)};p.update(kwargs)
            try:q,h=saved(*args,**kwargs)
            except RuntimeError as error:p.update(accepted=False,error=str(error));raise
            else:p.update(accepted=True,velocity=q,health=h);return q,h
            finally:
                api.require(len(records)<200,'capture budget');path=OUT/f'system_{len(records):03d}.json';api.write(path,p,raw=True);records.append({'path':str(path),'sha256':api.sha(path),'solver':p['solver'],'error':p.get('error')})
        hot.s50._finish=observe;hot.PRIMARY.__globals__['_finish']=observe
        try:
            q,h=c.diag.replay(field,geometry,spec,state,failure['dt_s']);error=None
        except RuntimeError as e:error=str(e)
        finally:hot.s50._finish=saved;hot.PRIMARY.__globals__['_finish']=compiled
    result={'matched_failure':error==failure['reason'],'error':error,'systems':records,'steps':0}
    api.write(OUT/'results.json',result);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('CAPTURE',result['matched_failure'],len(records),[(r['solver'],r['error']) for r in records[:8]])


if __name__=='__main__':main()
