"""Independent exact-rational squared-distance/Newton geometry verification."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
import copy, os, traceback
import numpy as np
import authenticate_failed_system_v1 as source
job, api, ROOT = source.job, source.api, source.ROOT
BASE=ROOT/'stage210_evaluations/three_contact_failure_20261001'
REPORT=BASE/'sphere_gap_arithmetic_01/results.json'
OUT=BASE/'sphere_gap_arithmetic_independent_02'


def exact(x):return F.from_float(float(x))


def decimal(x):return D(x.numerator)/D(x.denominator)


def rational_norm(v):
    square=sum(q*q for q in v);q=decimal(square)
    root=D(str(float(square)**.5))
    for _ in range(12):root=(root+q/root)/2
    assert abs(root*root-q)<D('1e-110')
    return root


def check(r,d,producer,data):
    spec=next(c for c in d['cases'] if c['id']=='s2_i124_sphere_f0p0625')['spec']
    a=spec['config']['prolate_semiaxes_m'][0];L=spec['field_metadata']['cell_length_m']
    x=producer['final_result']['checkpoint']['state']['x']
    held=api.read(source.OUT/'failed_systems.json')['failed_outer_trials'][0]['outer_inputs']
    assert r['new_trajectory_steps']==0 and r['original_gaps_not_changed'] and r['no_numerical_repair_installed']
    assert [z['grain_id'] for z in r['contacts']]==[28,141,185]
    with localcontext() as ctx:
        ctx.prec=120
        for z,contact in zip(r['contacts'],held[6]):
            k=z['grain_id'];c=data['sand_centres_m'][k];radius=data['sand_radii_m'][k]
            delta=c-np.array(x);images=np.round(delta/L);delta-=L*images;ci=np.array(x)+delta
            periodic=[exact(cc)-exact(xx)-exact(L)*exact(im) for cc,xx,im in zip(c,x,images)]
            rounded=[exact(cc)-exact(xx) for cc,xx in zip(ci,x)]
            ep=rational_norm(periodic)-decimal(exact(a)+exact(radius))
            ei=rational_norm(rounded)-decimal(exact(a)+exact(radius))
            assert abs(ep-D(z['exact_binary64_periodic_gap_m']))<D('1e-95')
            assert abs(ei-D(z['exact_binary64_rounded_image_gap_m']))<D('1e-95')
            assert z['saved_original_gap_m']==contact[1]
            assert abs(decimal(exact(contact[1]))-ei-D(z['original_minus_exact_image_gap_m']))<D('1e-95')
            for t in z['translated_original_formula']:assert t['gap_change_m']==t['gap_m']-contact[1]
    return True


def run():
    d=api.read(job.DESIGN);job.verify(d);r=api.read(REPORT)
    assert api.read(REPORT.parent/'completion.json')['results_sha256']==api.sha(REPORT)
    api.verify_mapping(r['inputs'])
    producer=api.read(job.RUN/'s2_i124_sphere_f0p0625/result.json')
    geo=next(c for c in d['cases'] if c['id']=='s2_i124_sphere_f0p0625')['spec']['field_metadata']['geometry']
    data=np.load(geo['path']);assert api.sha(geo['path'])==geo['sha256']
    failure=BASE/'sphere_gap_arithmetic_independent_preparation_01/failure.json'
    inputs={str(p):api.sha(p) for p in (Path(__file__),REPORT,source.WORK,job.DESIGN,failure,ROOT/'stage210_staging/verify_sphere_gap_arithmetic_v1.py')}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    try:
        assert check(r,d,producer,data);rejected=[]
        for field in ('saved_original_gap_m','exact_binary64_periodic_gap_m','exact_binary64_rounded_image_gap_m','original_minus_exact_image_gap_m'):
            bad=copy.deepcopy(r);old=bad['contacts'][0][field]
            bad['contacts'][0][field]=str(D(old)+D('1e-18')) if isinstance(old,str) else old+1e-18
            try:check(bad,d,producer,data)
            except AssertionError:rejected.append(field)
            else:raise AssertionError('corrupt arithmetic accepted '+field)
        api.verify_mapping(inputs)
        result=dict(independent_arithmetic_verification_passed=True,new_trajectory_steps=0,contacts_checked=3,corrupt_controls_rejected=rejected,inputs=inputs,
            claim='Independent exact-rational squared-distance/Newton comparator only. No replacement gaps, trajectory qualification, numerical pass or global frictional infeasibility claim. V1 missing optional dependency preserved.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')));print(result,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
