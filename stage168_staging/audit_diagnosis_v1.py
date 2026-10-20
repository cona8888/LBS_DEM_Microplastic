"""Read-only independent arithmetic audit and sealed diagnosis summary."""
import json,hashlib
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'stage168_evaluations/sphere_three_contact_diagnosis_20260923'
OUT=BASE/'diagnosis_01'


def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def require(x,message):
    if not x:raise RuntimeError(message)
def write(p,value):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)


def independent(p):
    f,A,z,g,v=np.array(p['force']),np.array(p['A']),np.array(p['z']),np.array(p['gaps']),np.array(p['vfree'])
    mu,dt=p['friction'],p['dt'];w=z+A@f;res=[];margins=[]
    for k in range(len(g)):
        i=3*k;step=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3]).max()
        res.append(abs(min(A[i,i]*f[i],w[i]+g[k]/dt)))
        trial=f[i+1:i+3]-w[i+1:i+3]/step
        projected=trial*min(1.,mu*f[i]/max(np.linalg.norm(trial),1e-300))
        res.append(np.linalg.norm(f[i+1:i+3]-projected)*step)
        margins.append(float(mu*f[i]-np.linalg.norm(f[i+1:i+3])))
    return {'residual':float(max(res)/max(np.linalg.norm(v),1e-15)),
            'cone_margins_N':margins,'cone_allowance_N':float(1e-12*max(np.linalg.norm(f),1e-30))}


def main():
    artifacts={}
    def bind(p):artifacts[str(p)]=sha(p);return read(p)
    cp=BASE/'capture_03';r=bind(cp/'results.json');seal=bind(cp/'completion.json')
    require(r['diagnostic_integrity_passed'] and seal['results_sha256']==sha(cp/'results.json'),'exact capture seal')
    require(r['probes'][0]['replay_difference_over_U']==0 and r['probes'][1]['error']=='direct contact cone violation','known-good identity and exact failed reason')
    design=ROOT/'stage168_designs/sphere_three_contact_diagnosis_20260923/design_03.json'
    d=bind(design);require(r['design_sha256']==sha(design),'capture design')
    for mapping in [d['inputs'],d['sources']]:
        for p,h in mapping.items():require(sha(p)==h,'bound input/source drift: '+p);artifacts[p]=h
    systems=[]
    for row in r['systems']:
        p=Path(row['path']);require(sha(p)==row['sha256'],'system drift');systems.append(bind(p))
    require(len(systems)==64 and sum(s['accepted'] for s in systems)==2,'capture accounting')
    main_metrics=independent(systems[2]);zero_metrics=independent(systems[3])
    require(main_metrics['residual']>1e-10,'primary residual independently fails')
    require(min(zero_metrics['cone_margins_N']) < -zero_metrics['cone_allowance_N'],'fallback cone independently fails')
    require(zero_metrics['residual']>1e-10,'fallback also fails residual; cone clipping alone insufficient')
    analysis=bind(BASE/'algebraic_analysis_01/results.json')
    for folder in ['algebraic_analysis_01','gap_sensitivity_01']:
        done=bind(BASE/folder/'completion.json');require(done['results_sha256']==sha(BASE/folder/'results.json'),'analysis seal')
        protocol=bind(BASE/folder/'protocol.json');source=ROOT/'stage168_staging'/('analyze_frozen_system_v1.py' if folder=='algebraic_analysis_01' else 'check_gap_sensitivity_v1.py')
        require(protocol['source_sha256']==sha(source),'analysis source');artifacts[str(source)]=sha(source)
        require(protocol['matrix_sha256']==sha(cp/'system_002.json'),'matrix binding')
    require(not analysis['admissible_candidate_found'] and analysis['trajectory_steps']==0,'no unqualified success')
    for candidate in analysis['independent_candidates']:
        fake=dict(systems[2],force=candidate['force']);m=independent(fake)
        require(m['residual']>1e-10 and np.isclose(m['residual'],candidate['residual'],rtol=1e-6,atol=1e-14),'independent candidate failure')
    sensitivity=bind(BASE/'gap_sensitivity_01/results.json')
    original,scaled,zero=sensitivity['tests']
    require(not original['passed'] and not scaled['passed'] and zero['passed'],'gap sensitivity result')
    zero_force=zero['health']['reactions']
    altered=independent(dict(systems[2],gaps=[0.,0.,0.],force=zero_force))
    restored=independent(dict(systems[2],force=zero_force))
    require(altered['residual']<=1e-10 and restored['residual']>1e-10,'counterfactual not original pass')
    require(min(altered['cone_margins_N'])>=-altered['cone_allowance_N'],'counterfactual cone')
    J=np.array(systems[2]['jacobian']);M=np.array(systems[2]['mobility']);A=np.array(systems[2]['A'])
    require(np.all(np.linalg.eigvalsh(M)>0) and np.linalg.cond(M)<4,'well-conditioned SPD six-DOF mobility')
    require(np.linalg.matrix_rank(J)==6 and np.linalg.matrix_rank(A)==6,'contact redundancy confirmed')
    q_target=np.zeros(9);q_target[::3]=-np.asarray(systems[2]['gaps'])/systems[2]['dt']
    q_fit=np.linalg.lstsq(J,q_target,rcond=1e-12)[0]
    gap_fit=float(np.linalg.norm(J@q_fit-q_target))
    require(gap_fit>1e-14,'nonzero exact all-stick mismatch')
    # Large frozen CPD6 data are independently rehashed, not merely trusted by path.
    for rel,h in [
        ('stage130_runs/cpd6_final_stationarity_20260916/gpu_confirmation_01/stage130_cpd6_final_stationarity/final_fields.npz','8cba5eb9857a09ba7c09bd3963db0d97855ccbdd037ea636dcca8e7961c62cad'),
        ('stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz','65c0f56a4f4b1434bb96b985565cedf3f270970c480fa7cfa968b79282714d2a')]:
        p=ROOT/rel;require(sha(p)==h,'CPD6 frozen binary');artifacts[str(p)]=h
    evidence={'audit_passed':True,'original_campaign_passed':False,'repair_qualified':False,
        'exact_positive_control':True,'exact_first_failure_reproduced':True,'main_candidate':main_metrics,
        'zero_seed_candidate':zero_metrics,'gap_counterfactual_under_zero_gaps':altered,'same_force_under_original_gaps':restored,
        'mobility_condition':float(np.linalg.cond(M)),'contact_matrix_rank':int(np.linalg.matrix_rank(A)),
        'gaps_m':systems[2]['gaps'],'gap_rates_m_s':(np.asarray(systems[2]['gaps'])/systems[2]['dt']).tolist(),
        'all_stick_least_squares_error_m_s':gap_fit,'recorded_rejected_finish_candidates':62,
        'extra_analytic_derivative_candidates_tested':3,'extra_gap_sensitivity_contact_solves':3,
        'nonadvancing_pose_probes_total_including_superseded_diagnostics':6,
        'trajectory_steps_advanced':0,'production_changed':False,
        'conclusion':'Near-rest three-contact sticking degeneracy and roundoff-scale nonzero gap correction expose a solver failure. No original-gap admissible candidate has been found. Existence/non-existence of another sliding/open solution is not established.',
        'boundaries':['Earlier non-matching capture_01 and capture_02 preserved; capture_03 is the matching replay.',
                      'Zero-gap sensitivity is not a permissible silent repair or qualification.',
                      'No trapping/release/validation claim; Stage167 remains failed and incomplete.'],
        'next':'Original-law contact-nullspace/active-set feasibility and bounded solver repair tests first. If geometric roundoff treatment must change, freeze it explicitly as a revised numerical contract; no automatic rerun.'}
    OUT.mkdir(exist_ok=False);artifacts[str(Path(__file__).resolve())]=sha(__file__)
    write(OUT/'results.json',evidence);write(OUT/'completion.json',{'audit_passed':True,'results_sha256':sha(OUT/'results.json'),'artifacts':artifacts})
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
