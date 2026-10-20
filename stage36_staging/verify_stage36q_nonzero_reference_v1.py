import json,platform
from pathlib import Path
import numpy as np
from numpy.polynomial import Polynomial as P
from numpy.polynomial.legendre import leggauss
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
R=.2;L=.4;MU=.1;AMP=.01;D=L-R
POLY=AMP*P([0,0,1])*P([1,-1])**4
def field(x):
    x=np.asarray(x);r=np.linalg.norm(x,axis=1);u=np.zeros_like(x);mask=(r>=R)&(r<=L);z=x[mask];r=r[mask];q=(r-R)/D
    f=POLY(q);fp=POLY.deriv()(q)/D
    u[mask]=-.5*(fp/r)[:,None]*z[:,0,None]*z;u[mask,0]+=f+.5*r*fp
    return u
def derivatives(x):
    r=np.linalg.norm(x,axis=1);n=x/r[:,None];q=(r-R)/D
    f1=POLY.deriv(1)(q)/D;f2=POLY.deriv(2)(q)/D**2;f3=POLY.deriv(3)(q)/D**3
    ap=1.5*f1+.5*r*f2;app=2*f2+.5*r*f3;b=-.5*f1/r;bp=-.5*(f2/r-f1/r**2);bpp=-.5*(f3/r-2*f2/r**2+2*f1/r**3)
    grad=bp[:,None,None]*x[:,:,None]*x[:,0,None,None]*n[:,None,:]+b[:,None,None]*x[:,0,None,None]*np.eye(3)
    grad[:,:,0]+=b[:,None]*x;grad[:,0,:]+=ap[:,None]*n
    lap=(bpp+6*bp/r)[:,None]*x[:,0,None]*x;lap[:,0]+=app+2*ap/r+2*b
    return grad,lap
def angular():
    z,w=leggauss(24);phi=np.arange(48)*2*np.pi/48;zz,pp=np.meshgrid(z,phi,indexing='ij');n=np.stack([np.sqrt(1-zz**2)*np.cos(pp),np.sqrt(1-zz**2)*np.sin(pp),zz],axis=-1).reshape(-1,3)
    return n,np.repeat(w,48)*2*np.pi/48
def main():
    parent=ROOT/'stage36_evaluations/stage36p_driven_comotion_20260908/verification_01/manifest.json';v=json.loads(parent.read_text());assert v['completed'];checked={str(parent):sha(parent)}
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h;checked[p]=h
    exact=np.array([4*np.pi/3*MU*R**3*2*AMP/D**2,0,0]);n,w=angular();tests={}
    tests['no_slip']=float(abs(field(R*n)).max())<1e-14;tests['compact_support']=float(abs(field(.45*n)).max())==0
    rng=np.random.default_rng(360);x=rng.normal(size=(100,3));x=x/np.linalg.norm(x,axis=1)[:,None]*rng.uniform(.22,.38,(100,1));G,lap=derivatives(x);h=1e-5
    Gfd=np.stack([(field(x+h*e)-field(x-h*e))/(2*h) for e in np.eye(3)],axis=2)
    lapfd=sum((field(x+h*e)-2*field(x)+field(x-h*e))/h**2 for e in np.eye(3))
    tests['divergence']=float(abs(np.trace(Gfd,axis1=1,axis2=2)).max())<1e-7;tests['gradient']=float(abs(G-Gfd).max())<1e-5;tests['laplacian']=float(abs(lap-lapfd).max())<1e-5
    forces=[]
    for h in (.001,.0005,.00025):
        dudr=(-3*field(R*n)+4*field((R+h)*n)-field((R+2*h)*n))/(2*h)
        traction=MU*(dudr+n*np.sum(dudr*n,axis=1)[:,None]);force=R**2*w@traction;error=float(np.linalg.norm(force-exact)/np.linalg.norm(exact));forces.append({'h':h,'force':force.tolist(),'relative_error':error})
    tests['wall_derivative_convergence']=forces[2]['relative_error']<.001 and forces[2]['relative_error']<forces[1]['relative_error']<forces[0]['relative_error']
    volumes=[]
    for nr in (32,64):
        rr,rw=leggauss(nr);rr=R+(rr+1)*D/2;rw=rw*D/2;pts=(rr[:,None,None]*n[None,:,:]).reshape(-1,3);weights=(rw[:,None]*rr[:,None]**2*w[None,:]).ravel()
        grad,lapa=derivatives(pts);u=field(pts);source=np.einsum('nij,nj->ni',grad,u)-MU*lapa;vol=weights@source;error=float(np.linalg.norm(vol-exact)/np.linalg.norm(exact));volumes.append({'radial_points':nr,'integrated_source':vol.tolist(),'relative_error':error})
    tests['source_integral']=all(v['relative_error']<1e-9 for v in volumes)
    out=ROOT/'stage36_evaluations/stage36q_nonzero_reference_20260908/reference_01';out.mkdir(parents=True,exist_ok=False)
    results={'tests':tests,'passed':all(tests.values()),'analytical_force_reference_units':exact.tolist(),'wall_derivative':forces,'source_integrals':volumes,'new_flow_solves':0}
    (out/'reference.json').write_text(json.dumps(results,indent=2));np.savez_compressed(out/'reference_samples.npz',points=x,velocity=field(x),gradient=G,laplacian=lap)
    (out/'RESULTS.md').write_text('# Stage36Q — independent nonzero force comparator\n\n'+json.dumps(results,indent=2)+'\n\nThese are reference-function checks, not LBM flow simulations. The analytical force is derived from exterior surface stress; integrated prescribed volume forcing provides a separate continuum check. A stationary no-slip sphere experiences nonzero traction in this manufactured recirculating flow. No experimental or physical drag validation is claimed.\n\nNext: implement and run the solver against this frozen source and force history; preserve spatial/time resolution failures. The existing3.68% discrepancy remains unresolved.\n')
    contract=ROOT/'stage36_staging/STAGE36Q_NONZERO_REFERENCE_CONTRACT.md';sources={str(Path(__file__).resolve()):sha(__file__),str(contract):sha(contract)}
    (out/'manifest.json').write_text(json.dumps({'completed':True,'reference_passed':all(tests.values()),'source_hashes':sources,'input_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'production_authorized':False},indent=2))
    print(json.dumps(results,indent=2));assert all(tests.values())
if __name__=='__main__':main()
