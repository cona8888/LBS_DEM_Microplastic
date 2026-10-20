"""Independent limiting cases for repaired sampling and rigid contact primitives."""
import argparse,json,hashlib,time
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
import transport_contact as m

ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();checks={};values={}
def test(name,condition,value):checks[name]=bool(condition);values[name]=value
x,y,z=np.meshgrid(*(np.arange(12)+.5 for _ in range(3)),indexing='ij')
v=np.array([2*x-3*y+z,x+y,2*z]);f=m.CellField(v,1.)
pos=np.array([3.2,4.3,5.7]);u,g=f.sample(pos)
err=float(np.max(abs(u-[2*pos[0]-3*pos[1]+pos[2],pos[0]+pos[1],2*pos[2]])))
test('cell_centre_linear',err<1e-12,err);err=float(np.max(abs(g-[[2,-3,1],[1,1,0],[0,0,2]])))
test('linear_gradient',err<1e-12,err)
up,_=f.sample(pos+[12,0,0]);test('periodic_field',np.max(abs(up-u))<1e-12,float(np.max(abs(up-u))))
try:m.CellField(np.full_like(v,np.nan),1.);reject=False
except FloatingPointError:reject=True
test('nonfinite_rejected',reject,reject)
fluid=np.ones((12,12,12),bool);fluid[3,4,5]=False
try:m.CellField(v,1.,fluid).sample(pos);reject=False
except ValueError:reject=True
test('mixed_stencil_rejected',reject,reject)
te=m.linear_pose_exit_time([9,5,5],[1,0,0],[2,0,0,0,0,0],1,1,10,2.)
test('full_body_exit',abs(te-1)<1e-12,float(te))
gap,normal,lever=m.ellipsoid_grain_contact([0,0,0],[1,0,0],4,1,[2,2,0],.1)
test('ellipsoid_false_interception_removed',gap>1,float(gap))
surface=(lever[0]/4)**2+lever[1]**2+lever[2]**2
nn=m.unit(lever/np.array([16,1,1]));test('closest_point_surface_normal',abs(surface-1)<1e-11 and np.linalg.norm(nn+normal)<1e-10,[float(surface),float(np.linalg.norm(nn+normal))])
sg=m.ellipsoid_grain_contact([0,0,0],[1,0,0],1,1,[3,0,0],1)[0]
test('sphere_gap_exact',abs(sg-1)<1e-12,float(sg))
gr=m.GrainGeometry([[.2,5,5]],[1],10)
c1=gr.contacts([9,5,5],[1,0,0],.4,.4,1)[0][1];c2=gr.contacts([-1,5,5],[1,0,0],.4,.4,1)[0][1]
test('periodic_unwrapped_gap',abs(c1-c2)<1e-12,float(abs(c1-c2)))
rt,rr=m.resistance_axes(1.,1.,1.);err=float(max(np.max(abs(rt/(6*np.pi)-1)),np.max(abs(rr/(8*np.pi)-1))))
test('stokes_translation_rotation',err<1e-10,err)
p=m.unit([1,2,3]);M=m.mobility(p,4,1,1);test('mobility_positive_symmetric',np.linalg.eigvalsh(M).min()>0 and np.linalg.norm(M-M.T)<1e-14,float(np.linalg.eigvalsh(M).min()))
contact=[(0,0.,np.array([1.,0,0]),np.zeros(3))]
vv,info=m.contact_solve(np.array([-1.,1,0,0,0,0]),np.eye(6),contact,1,1,.3)
test('coulomb_slip',np.max(abs(vv-[0,.7,0,0,0,0]))<1e-9,{'velocity':vv.tolist(),**info})
vv,info=m.contact_solve(np.array([-1.,.1,0,0,0,0]),np.eye(6),contact,1,1,.3)
test('coulomb_stick',np.linalg.norm(vv)<1e-9,{'velocity':vv.tolist(),**info})
vv,info=m.contact_solve(np.array([1.,.1,0,0,0,0]),np.eye(6),contact,1,1,.3)
test('separation_no_attraction',np.max(abs(vv-[1,.1,0,0,0,0]))<1e-12,vv.tolist())
wedge=contact+[(1,0.,np.array([0.,1,0]),np.zeros(3))]
vv,info=m.contact_solve(np.array([-1.,-1,1,0,0,0]),np.eye(6),wedge,1,1,0.)
test('two_contact_wedge',np.max(abs(vv-[0,0,1,0,0,0]))<1e-9,{'velocity':vv.tolist(),**info})
torque=[(0,0.,np.array([0.,1,0]),np.array([1.,0,0]))]
vv,info=m.contact_solve(np.array([0.,-1,0,0,0,0]),np.eye(6),torque,1,1,0.)
test('offcentre_contact_torque',np.max(abs(vv-[0,-.5,0,0,0,.5]))<1e-9,{'velocity':vv.tolist(),**info})
# Analytical Jeffery solution p proportional to (ar*cos(t/(ar+1/ar)), -sin(...),0).
ar=4.;g=np.array([[0,1,0],[0,0,0],[0,0,0]],float);T=4.;exact=m.unit([ar*np.cos(T/(ar+1/ar)),-np.sin(T/(ar+1/ar)),0])
errs=[]
for dt in [.04,.02,.01]:
    p=np.array([1.,0,0])
    for _ in range(round(T/dt)):p=m.midpoint_orientation(p,g,ar,dt)
    errs.append(float(np.linalg.norm(p-exact)))
test('jeffery_three_level_convergence',errs[2]<1e-4 and errs[0]/errs[1]>3.5 and errs[1]/errs[2]>3.5,errs)
# A rotating body's exit root must include changing axial support.
x0=np.array([9.,0,0]);p0=np.array([0.,1,0]);vel=np.array([2.,0,0,0,0,2.])
te=m.linear_pose_exit_time(x0,p0,vel,2,1,10,3.)
xx,pp=m.advance_pose(x0,p0,vel,2,te);test('rotating_full_exit',abs(m.full_exit_function(xx,pp,2,1,10))<1e-9,float(te))
result={'passed':all(checks.values()),'checks':checks,'values':values,'runtime_seconds':time.perf_counter()-start,'hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(m.__file__)]},'scope':'primitive verification; full trajectory and near-wall applicability require separate gates'}
(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
