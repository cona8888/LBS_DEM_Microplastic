"""Independent rational/120-digit zero-step verification; no solver invocation."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
import copy, math, os, shutil, sys, traceback
import numpy as np
import psutil
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage210_staging'))
import authenticate_failed_system_v1 as source
job, api = source.job, source.api
BASE = ROOT / 'stage212_evaluations/roundoff_gap_20261001'
REPORT = BASE / 'qualification_02/results.json'
CONTRACT = ROOT / 'stage212_designs/roundoff_gap_20261001/contract_02.json'
OUT = BASE / 'independent_01'
EXPECTED_REPORT = '42e9d724cd656564e9da66b492de80dc87a0a5de348aa1a90cf66d0c2801da11'

def need(ok, why):
    if not ok: raise AssertionError(why)

def frac(x): return F.from_float(float(x))
def dec(x): return D(x.numerator) / D(x.denominator) if isinstance(x,F) else D.from_float(float(x))
def norm(x): return sum(z*z for z in x).sqrt()
def mv(M,v): return [sum(a*b for a,b in zip(row,v)) for row in M]
def transpose(M): return list(map(list,zip(*M)))
def matmul(A,B): return [mv(transpose(B),r) for r in A]

def inverse_apply(M,v):
    a=[row[:] + [q] for row,q in zip(M,v)]
    for k in range(len(v)):
        pivot=max(range(k,len(v)),key=lambda i:abs(a[i][k])); a[k],a[pivot]=a[pivot],a[k]
        need(a[k][k]!=0,'invertible mobility')
        scale=a[k][k];a[k]=[z/scale for z in a[k]]
        for i in range(len(v)):
            if i!=k:
                scale=a[i][k];a[i]=[x-scale*y for x,y in zip(a[i],a[k])]
    return [row[-1] for row in a]

def validate_policy(record, x, c, a, r):
    need(record['policy']=='stage212_binary64_sphere_gap_band_v1' and record['sphere'], 'exact policy/domain')
    need(record['operations']==64 and record['unit_roundoff']==2.0**-53
         and record['maximum_band_over_body_radius']==1e-10,'fixed prior policy constants')
    scale=sum(map(lambda z:abs(frac(z)),[*x,*c,a,r]),F(0))
    u=F(1,2**53); exact_band=64*u/(1-64*u)*scale; band=frac(record['uncertainty_m'])
    need(exact_band<=band<=exact_band*(1+F(1,10**14)), 'outward rounding and bounded arithmetic band')
    need(0<band<=frac(1e-10)*frac(a),'relative-radius ceiling')
    raw=record['raw_gap_m']; zero=abs(frac(raw))<=band
    need(record['classified_zero']==zero and record['changed']==(zero and raw!=0),'classification flags')
    expected=0.0 if zero else float(raw)
    need(float(record['effective_gap_m']).hex()==expected.hex(),'effective operand and outside bit identity')
    return band

def validate_geometry(report, design, evidence):
    need(report['new_trajectory_steps']==0 and not report['production_authorized']
         and report['old_campaign_remains_failed'] and report['revised_gap_policy_explicit'], 'nonpromotion/zero-step disclosure')
    spec=next(c['spec'] for c in design['cases'] if c['id']=='s2_i124_sphere_f0p0625')
    axes=spec['config']['prolate_semiaxes_m'];need(len(axes)==3 and axes[0]==axes[1]==axes[2],'sphere')
    a=axes[0];L=spec['field_metadata']['cell_length_m']; geo=spec['field_metadata']['geometry']
    need(api.sha(geo['path'])==geo['sha256'],'geometry seal'); data=np.load(geo['path'],allow_pickle=False)
    producerpath=job.RUN/'s2_i124_sphere_f0p0625/result.json'
    need(api.read(producerpath.parent/'completion.json')['result_sha256']==api.sha(producerpath),'producer seal')
    state=api.read(producerpath)['final_result']['checkpoint']['state']; x=np.asarray(state['x'],float)
    contacts=evidence['failed_outer_trials'][0]['outer_inputs'][6]
    need(len(report['contexts'])==3 and len(report['boundary_geometry_checks'])==21,'all geometry controls')
    records=[]
    for n,(z,contact) in enumerate(zip(report['contexts'],contacts)):
        k,raw,normal,lever=contact; centre=data['sand_centres_m'][k];radius=float(data['sand_radii_m'][k])
        delta=centre-x;delta-=L*np.round(delta/L);c=x+delta
        need(z['grain_id']==k and z['x']==x.tolist() and z['c']==c.tolist()
             and z['a']==z['b']==a and z['r']==radius and z['raw_gap_m']==raw,'original geometry identity')
        band=validate_policy(z,x,c,a,radius)
        square=sum((frac(cc)-frac(xx))**2 for cc,xx in zip(c,x))
        q=dec(square);root=D(str(float(square)**0.5))
        for _ in range(12):root=(root+q/root)/2
        need(abs(root*root-q)<D('1e-110'),'120-digit Newton distance verification')
        exact_gap=root-dec(frac(a)+frac(radius));error=abs(dec(raw)-exact_gap)
        need(error<=dec(band) and abs(exact_gap)<=dec(band),'observed native error/true gap inside band')
        rows=[t for t in report['boundary_geometry_checks'] if t['context']==n]
        bandf=float(z['uncertainty_m'])
        expected=[0.,bandf,-bandf,math.nextafter(bandf,math.inf),-math.nextafter(bandf,math.inf),1e-8*a,-1e-8*a]
        need([t['test_gap_m'] for t in rows]==expected,'all signed boundary/outside inputs')
        for t in rows:
            need(t['raw_gap_m']==t['test_gap_m'],'boundary provenance');validate_policy(t,x,c,a,radius)
        records.append(dict(grain_id=k, exact_binary_image_gap_m=str(exact_gap),native_error_m=str(error),band_m=z['uncertainty_m']))
    need(set(report['invalid_input_controls_rejected'])=={'nan_gap','negative_radius','nonfinite_centre','coordinate_scale_ceiling'},'all invalid controls')
    return records

def validate_held(row,item,contexts):
    s=item['system'];need(api.digest(s)==item['system_sha256'],'held source seal')
    need(row['original_system']==s and row['original_system_sha256']==item['system_sha256']
         and row['raw_gaps_m']==s['gaps_m'] and row['dt_s']==s['dt_s'] and row['accepted'], 'exact raw equations/passing candidate')
    need(row['policy']=='stage212_binary64_sphere_gap_band_v1','held policy identity')
    expected=[0. if abs(frac(g))<=frac(c['uncertainty_m']) else g for g,c in zip(s['gaps_m'],contexts)]
    need(row['effective_gaps_m']==expected,'held revised-gap provenance')
    v=[dec(z) for z in s['vfree']];M=[[dec(z) for z in r] for r in s['mobility']]
    J=[[dec(z) for z in r] for r in s['jacobian']];f=[dec(z) for z in row['health']['reactions']]
    velocity=[dec(z) for z in row['velocity']];mu=dec(s['friction']);dt=dec(s['dt_s'])
    need(len(f)==9 and len(velocity)==6 and len(expected)==3,'full three-contact six-DOF')
    JT=transpose(J);A=matmul(matmul(J,M),JT);z=mv(J,v)
    affine=[x+y for x,y in zip(z,mv(A,f))];actual=mv(J,velocity)
    scale=max(norm(v),D('1e-15'));fs=max(norm(f),D('1e-30'));residual=D(0);actual_residual=D(0)
    for k,g in enumerate(expected):
        i=3*k;need(f[i]>=0,'nonnegative normal')
        need(norm(f[i+1:i+3])<=mu*f[i]+D('1e-12')*fs,'unchanged Coulomb cone')
        ii,jj=A[i+1][i+1],A[i+2][i+2];ij=(A[i+1][i+2]+A[i+2][i+1])/2
        step=(ii+jj+((ii-jj)**2+4*ij**2).sqrt())/2;need(step>0,'positive tangent step')
        for vv,label in ((affine,'affine'),(actual,'actual')):
            trial=[f[t]-vv[t]/step for t in (i+1,i+2)];length=norm(trial)
            shrink=min(D(1),mu*f[i]/max(length,D('1e-300')))
            tang=norm([f[t]-trial[t-i-1]*shrink for t in (i+1,i+2)])*step
            rr=max(abs(min(A[i][i]*f[i],vv[i]+dec(g)/dt)),tang)
            if label=='affine':residual=max(residual,rr)
            else:actual_residual=max(actual_residual,rr)
    generalized=mv(JT,f); recovered=inverse_apply(M,[a-b for a,b in zip(velocity,v)])
    closure=norm([a-b for a,b in zip(recovered,generalized)])/max(norm(generalized),D('1e-30'))
    work=sum(f[3*k+j]*affine[3*k+j] for k in range(3) for j in (1,2))
    need(residual/scale<=D('1e-10') and actual_residual/scale<=D('1e-10'),'unchanged affine and returned-velocity residual')
    need(closure<=D('1e-8') and work<=D('1e-8')*fs*scale,'unchanged force closure/dissipation')
    need(row['health']['residual']<=1e-10 and row['health']['force_residual']<=1e-8,'original reported health')
    return dict(dt_s=s['dt_s'], rational_decimal_affine_relative_residual=str(residual/scale),
                returned_velocity_relative_residual=str(actual_residual/scale),force_closure=str(closure),friction_work=str(work))

def run():
    need(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'threads1')
    need(shutil.disk_usage(ROOT).free>=21474836480,'20GiB reserve')
    need(not source.frozen.active_owned(False) and not OUT.exists(),'exclusive independent zero-step audit')
    contract=api.read(CONTRACT);api.verify_mapping(contract['sources']);api.verify_mapping(contract['inputs'])
    need(api.sha(REPORT)==EXPECTED_REPORT and api.read(REPORT.parent/'completion.json')['results_sha256']==EXPECTED_REPORT,'candidate seal')
    report=api.read(REPORT);api.verify_mapping(report['inputs']);api.verify_mapping(report['artifacts'])
    design=api.read(job.DESIGN);job.verify(design);evidence=api.read(source.OUT/'failed_systems.json')
    inputs={str(p):api.sha(p) for p in (Path(__file__),CONTRACT,REPORT,REPORT.parent/'completion.json',source.OUT/'failed_systems.json')}
    OUT.mkdir(parents=True,exist_ok=False);process=psutil.Process()
    job.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),new_trajectory_steps=0,inputs=inputs))
    try:
        with localcontext() as ctx:
            ctx.prec=120
            geometry=validate_geometry(report,design,evidence)
            need(len(report['artifacts'])==report['held_passes']==report['held_system_count']==30 and report['all_held_systems_passed'],'full held inventory')
            rows=[api.read(REPORT.parent/('held_%02d.json'%i)) for i in range(30)]
            metrics=[validate_held(row,item,report['contexts']) for row,item in zip(rows,evidence['failed_inner_systems'])]
            rejected=[]
            for name in ('band','raw_gap','effective_gap','zero_step_disclosure'):
                bad=copy.deepcopy(report)
                if name=='band':bad['contexts'][0]['uncertainty_m']*=2
                elif name=='raw_gap':bad['contexts'][0]['raw_gap_m']+=1e-12
                elif name=='effective_gap':bad['contexts'][0]['effective_gap_m']=1e-12
                else:bad['new_trajectory_steps']=1
                try:validate_geometry(bad,design,evidence)
                except AssertionError:rejected.append(name)
                else:raise AssertionError('corrupt geometry accepted '+name)
            for name in ('held_raw','held_effective','held_velocity','held_force','held_dt'):
                bad=copy.deepcopy(rows[0])
                if name=='held_raw':bad['raw_gaps_m'][0]=0.
                elif name=='held_effective':bad['effective_gaps_m'][0]=1e-12
                elif name=='held_velocity':bad['velocity'][0]+=1e-6
                elif name=='held_force':bad['health']['reactions']=[0.]*9
                else:bad['dt_s']*=2
                try:validate_held(bad,evidence['failed_inner_systems'][0],report['contexts'])
                except AssertionError:rejected.append(name)
                else:raise AssertionError('corrupt held result accepted '+name)
        api.verify_mapping(inputs);api.verify_mapping(report['artifacts']);api.verify_mapping(contract['sources']);api.verify_mapping(contract['inputs']);job.verify(design)
        need(shutil.disk_usage(ROOT).free>=21474836480,'final reserve')
        result=dict(independent_zero_step_policy_verification_passed=True,held_systems_independently_passed=30,
                    new_trajectory_steps=0,production_authorized=False,old_campaign_remains_failed=True,
                    geometry=geometry,held_metrics=metrics,negative_controls_rejected=rejected,inputs=inputs,
                    solver_health_original_gaps_preserved_is_relative_to_provided_effective_operands_not_old_raw_gaps=True,
                    claim='Explicit revised sphere gap operand policy passes these captured held systems only. No original-contract promotion, full-stack/trajectory qualification, production approval, six-case completion, population release or empirical validation.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print('INDEPENDENT_REVISED_GAP_PASS',len(metrics),len(rejected),api.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
