"""Final in-domain verification for inertial_contact_v2."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import inertial_contact_v2 as model

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
kinetic=lambda H,q:float(.5*q@H@q)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
 rp,rf,mu=1380.,998.2,.001002;a,b=2e-4,5e-5;deq=2*(a*b*b)**(1/3);phi=model.finite_re.prolate_sphericity(a,b)
 H,_=model.generalized_mass_matrix([1,0,0],a,b,rp,rf,0);Ha,ma=model.generalized_mass_matrix([1,0,0],a,b,rp,rf,1);_,ms=model.generalized_mass_matrix([1,0,0],b,b,rp,rf,1)
 R=model.stokes_generalized_resistance([1,0,0],a,b,mu);Z=np.zeros((6,6));initial=np.array([.002,-.001,.0005,.0002,-.0001,.00015]);T=5*H[0,0]/R[0,0];conv=[]
 for steps in (64,128,256):
  q=initial.copy();dt=T/steps
  for _ in range(steps):q,h=model.inertial_contact_step(q,np.zeros(6),np.zeros(6),R,Z,H,[],a,dt,0,1e-12,1,1,phi)
  exact=initial*np.exp(-np.diag(R)/np.diag(H)*T);conv.append({'steps':steps,'error':float(np.linalg.norm(q-exact)/np.linalg.norm(initial)),'health':h})
 plane=[(0,0.,np.array([0.,1,0]),np.array([0.,-b,0]))];old=np.array([.003,-.01,0,0,0,0.]);tiny=np.eye(6)*1e-12
 impact,hi=model.inertial_contact_step(old,np.zeros(6),np.zeros(6),tiny,Z,H,plane,a,1e-4,0,rf,mu,deq,phi)
 slide,hs=model.inertial_contact_step(old,np.zeros(6),np.zeros(6),tiny,Z,H,plane,a,1e-4,.3,rf,mu,deq,phi)
 wedge=plane+[(1,0.,np.array([0.,-1,0]),np.array([0.,b,0]))];wv,hw=model.inertial_contact_step(np.array([.001,.004,0,0,0,0.]),np.zeros(6),np.zeros(6),tiny,Z,H,wedge,a,1e-4,0,rf,mu,deq,phi)
 bg=np.array([.001,0,0,0,0,0.]);L=Z.copy();L[0,0]=R[0,0]
 nowall,hn=model.inertial_contact_step(bg,bg,np.zeros(6),R,Z,H,[],a,1e-3,0,rf,mu,deq,phi)
 wall,hf=model.inertial_contact_step(bg,bg,np.zeros(6),R,L,H,[],a,1e-3,0,rf,mu,deq,phi)
 mult=hf['finite_re_multiplier'];expected=(H[0,0]/1e-3+mult*R[0,0])*bg[0]/(H[0,0]/1e-3+mult*R[0,0]+L[0,0])
 health=[hi,hs,hw,hn,hf];checks={
  'all_finite_re_tests_within_re3':max(x['reynolds'] for x in health)<=3,
  'sphere_added_mass_half_displaced':max(abs(x-.5) for x in ms['added_mass_coefficients'])<=1e-15,
  'prolate_added_mass_anisotropic_positive':0<ma['added_mass_coefficients'][0]<ma['added_mass_coefficients'][1],
  'added_mass_positive_semidefinite':np.linalg.eigvalsh(Ha-H).min()>=-1e-20,
  'linear_relaxation_converges':conv[-1]['error']<=5e-4 and conv[-1]['error']<conv[-2]['error']<conv[-3]['error'],
  'impact_nonpenetrating':impact[1]>=-1e-10,'friction_reduces_tangential_speed':abs(slide[0])<abs(impact[0]),
  'unforced_energy_nonincreasing':kinetic(H,impact)<=kinetic(H,old) and kinetic(H,slide)<=kinetic(H,old),
  'wedge_normal_velocity_zero':abs(wv[1])<=1e-10,'fluid_following_without_wall':np.linalg.norm(nowall-bg)<=1e-14,
  'fixed_wall_nonlinear_comparator':wall[0]<bg[0] and abs(wall[0]-expected)<=1e-12,
  'all_momentum_residuals':max(x['momentum_residual'] for x in health)<=1e-8,
  'all_contact_fixed_points':max(x['contact']['residual'] for x in (hi,hs,hw))<=1e-8}
 sources=[Path(__file__),Path(model.__file__),Path(model.base.__file__),Path(model.contact_model.__file__),Path(model.finite_re.__file__)];result={'completed':True,'passed':all(checks.values()),'checks':{k:bool(v) for k,v in checks.items()},'values':{'maximum_test_reynolds':max(x['reynolds'] for x in health),'linear_convergence':conv,'no_wall_velocity':nowall.tolist(),'fixed_wall_velocity':wall.tolist(),'fixed_wall_expected_x':expected,'fixed_wall_multiplier':mult,'impact_velocity':impact.tolist(),'sliding_velocity':slide.tolist(),'wedge_velocity':wv.tolist(),'health':health},'source_hashes':{str(p.resolve()):sha(p) for p in sources},'supersedes_comparator_error':'../inertial_contact_verification_03','scope':'in-domain distinct-frame inertial/contact primitive; no matrix release claim'}
 (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'checks':result['checks'],'values':{k:result['values'][k] for k in ['maximum_test_reynolds','fixed_wall_velocity','fixed_wall_expected_x']}},indent=2))
if __name__=='__main__':main()
