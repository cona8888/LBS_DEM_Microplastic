"""Physical regime and independent resistance challenge before matrix execution."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import transport_contact as m

R=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
cfgp=R/'stage37_designs/release_contact_pilot_v1.json';cfg=json.loads(cfgp.read_text());phys=cfg['physics_scenarios'];a,b,_=cfg['initial_morphology']['prolate_semiaxes_m'];mu=phys['water_viscosity_Pa_s'];rhof=phys['water_density_kg_m3'];rhop=phys['PET_density_kg_m3'];gravity=np.array(phys['gravity_m_s2']);U=phys['target_pore_speed_m_s'];nu=mu/rhof
hashes={str(cfgp):hashlib.sha256(cfgp.read_bytes()).hexdigest(),str(Path(m.__file__).resolve()):hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()}
def load_result(path):
    d=json.loads(path.read_text());assert d['passed'] and all(d['checks'].values())
    hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest();return d
iso=R/'stage36_evaluations/stage36au_resistance_20260911/verification_01';ir=load_result(iso/'results.json');ip=iso/'resistance_n1024.npy'
assert hashlib.sha256(ip.read_bytes()).hexdigest()==ir['artifacts'][ip.name]
refR=np.load(ip);M=m.mobility([1,0,0],2,1,.1);analyticR=np.linalg.inv(M)
isolated_error=float(np.linalg.norm(analyticR-refR)/np.linalg.norm(refR));hashes[str(ip)]=hashlib.sha256(ip.read_bytes()).hexdigest()
cavity=R/'stage36_evaluations/stage36az_mobility_20260911/verification_01';cr=load_result(cavity/'results.json');cp=cavity/'operator.npz'
assert hashlib.sha256(cp.read_bytes()).hexdigest()==cr['operator_hash'];hashes[str(cp)]=hashlib.sha256(cp.read_bytes()).hexdigest()
with np.load(cp) as z:refM=z['mobility'].copy()
loads=list(np.eye(6))+[(np.eye(6)[i]+np.eye(6)[(i+1)%6])/np.sqrt(2) for i in range(6)]
rows=[]
for i,force in enumerate(loads):
    exact=refM@force;candidate=M@force
    rows.append({'load_id':i,'scaled_load':force.tolist(),'relative_generalized_velocity_error':float(np.linalg.norm(candidate-exact)/np.linalg.norm(exact))})
regimes=[]
for scale in [1.,.5,.25]:
    for shape in ['sphere','prolate']:
        aa,bb=((a*b*b)**(1/3),)*2 if shape=='sphere' else (a,b)
        aa*=scale;bb*=scale;volume=4*np.pi*aa*bb*bb/3
        rt,rr=m.resistance_axes(aa,bb,mu)
        for orientation,p in [('parallel',[0,0,1]),('perpendicular',[1,0,0])]:
            if shape=='sphere' and orientation=='perpendicular':continue
            v,_=m.free_motion(p,np.zeros((3,3)),[0,0,0],aa,bb,mu,rhop,rhof,gravity)
            slip=np.linalg.norm(v[:3]);tau=rhop*volume/min(rt)
            re=float(2*aa*(slip+U)/nu);st=float(tau*(slip+U)/bb)
            I=np.pi*bb**4/4;shear=(slip+U)/bb
            bend=mu*shear*(2*aa)**4/(phys['Young_modulus_Pa_for_rigidity_check']*I)
            regimes.append({'scale':scale,'shape':shape,'gravity_orientation':orientation,'unbounded_slip_estimate_m_s':float(slip),'conservative_body_Re_estimate':re,'response_St_estimate':st,'bending_ratio_estimate':float(bend),'creeping_pass':bool(re<=.1),'overdamped_pass':bool(st<=.01),'rigid_pass':bool(bend<=.01),'interpretation':'regime screening using Stokes resistance; if Re fails the estimated slip itself needs finite-Re correction'})
baseline=[x for x in regimes if x['scale']==1]
checks={'isolated_resistance_independent_error_below_0p001':isolated_error<.001,
 'confined_resistance_error_below_5percent':max(x['relative_generalized_velocity_error'] for x in rows)<=.05,
 'baseline_creeping_flow':all(x['creeping_pass'] for x in baseline),
 'baseline_overdamped':all(x['overdamped_pass'] for x in baseline),
 'baseline_rigidity_scale':all(x['rigid_pass'] for x in baseline),
 'matched_porosity_field_feedback_qualified':False,
 'representative_12_pose_matrix_validation_complete':False}
result={'passed':all(checks.values()),'checks':checks,'isolated_resistance_relative_error':isolated_error,'cavity_challenge':{'geometry':'one independent AR2 cavity pose; 12 load directions, not 12 poses and not a soil replica','rows':rows},'regimes':regimes,'stage4_physical_pilot_ready':False,'decision':'free-body mobility cannot be promoted to confined matrix contact transport; add verified wall/near-grain resistance and finite-Re treatment or narrow physical domain','hashes':hashes}
(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({'passed':result['passed'],'checks':checks,'isolated_error':isolated_error,'cavity_error_range':[min(x['relative_generalized_velocity_error'] for x in rows),max(x['relative_generalized_velocity_error'] for x in rows)],'regimes':regimes},indent=2))
