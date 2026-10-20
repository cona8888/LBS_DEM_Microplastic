"""Bounded independent one-grain challenge for reduced ambient-flow motion.

Reuses qualified MFS kernels; all geometry-dependent operators are rebuilt.
No trajectory or matrix campaign is launched by this reference calculation.
"""
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np
from scipy.linalg import svd
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'stage36_staging'))
import sharp_stokes_mfs_v3 as mfs
import sharp_sphere_reference_v1 as sphere
import transport_contact as reduced

def reference(centre,Q,axes,n):
    centre=np.array(centre,float);axes=np.array(axes,float)
    dirs=mfs.directions(n);bd=mfs.directions(3*n)
    sources=np.vstack([.6*dirs,centre+(dirs*np.sqrt(axes**2-(1-.55**2)*min(axes)**2))@Q.T])
    points=np.vstack([bd,centre+(bd*axes)@Q.T])
    A=mfs.kernel(points,sources,1.).transpose(0,2,1,3).reshape(18*n,6*n)
    left,s,right=svd(A,full_matrices=False);keep=s>s[0]*1e-12
    target=np.zeros((6*n,3,7));target[:,:,0]=[-1,0,0]
    for j in range(3):
        target[3*n:,:,j+1]=np.eye(3)[j]
        target[3*n:,:,j+4]=np.cross(np.eye(3)[j],points[3*n:]-centre)
    lam=(right[keep].T@((left[:,keep].T@target.reshape(18*n,7))/s[keep,None])).reshape(2*n,3,7)
    lever=sources[n:]-centre
    wrench=np.vstack([lam[n:].sum(axis=0),np.stack([np.cross(lever,lam[n:,:,j]).sum(axis=0) for j in range(7)],axis=1)])
    motion=np.linalg.solve(wrench[:,1:],-wrench[:,0]);strength=lam[:,:,0]+np.einsum('ncd,d->nc',lam[:,:,1:],motion)
    state={'sources':sources,'mu':1.};sol={'lambda':strength,'far_velocity':np.array([1.,0,0])}
    points,_,_=sphere.surface_quadrature(1.,24,48);errors=[]
    for boundary,is_body in [(points,False),(centre+(points*axes)@Q.T,True)]:
        errors.append(max(float(np.linalg.norm(mfs.velocity(state,sol,z)-(motion[:3]+np.cross(motion[3:],z-centre) if is_body else 0),axis=1).max()) for z in np.array_split(boundary,8)))
    balance=np.r_[strength[n:].sum(axis=0),np.cross(lever,strength[n:]).sum(axis=0)]
    return motion,{'boundary_error':max(errors),'force_torque_residual':float(np.linalg.norm(balance)),'condition':float(s[0]/s[-1])}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--count',type=int,default=384);ap.add_argument('--cases',type=int,default=12);args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False);rows=[]
    # Two size scales, two shapes, three positions: 12 independent poses.
    cases=[]
    for scale in [1.,.25]:
        for shape in ['sphere','prolate']:
            a=.0002/.000385*scale;b=.00005/.000385*scale
            axes=np.array([(a*b*b)**(1/3)]*3) if shape=='sphere' else np.array([a,b,b])
            for gap in [.5,.2,.08]:
                centre=np.array([0.,1.+axes[1]+gap,0.]);cases.append((scale,shape,axes,gap,centre))
    for index,(scale,shape,axes,gap,centre) in enumerate(cases[:args.cases]):
        start=time.perf_counter();motion,health=reference(centre,np.eye(3),axes,args.count)
        u=sphere.fields(centre[None,:],1,1,np.array([1.,0,0]))[0][0];g=np.empty((3,3));h=1e-5
        for j in range(3):
            d=np.eye(3)[j]*h;g[:,j]=(sphere.fields((centre+d)[None,:],1,1,[1,0,0])[0][0]-sphere.fields((centre-d)[None,:],1,1,[1,0,0])[0][0])/(2*h)
        pred,_=reduced.free_motion([1,0,0],g,u,axes[0],axes[1],1,1,1,[0,0,0]);pred[3:]/=axes[0]
        err=float(np.linalg.norm(pred[:3]-motion[:3])/max(np.linalg.norm(motion[:3]),.01))
        ang=float(np.linalg.norm(pred[3:]-motion[3:])*axes[0])
        row={'id':index,'shape':shape,'scale':scale,'axes':axes.tolist(),'gap_grain_radii':gap,'centre':centre.tolist(),'reference':motion.tolist(),'reduced':pred.tolist(),'translation_relative_error':err,'rotation_absolute_times_body_length':ang,'health':health,'reference_passed':health['boundary_error']<=.001 and health['force_torque_residual']<=1e-8,'reduced_passed':err<=.05 and ang<=.01,'seconds':time.perf_counter()-start}
        rows.append(row);(out/f'case_{index:02}.json').write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True)
    result={'passed':all(x['reference_passed'] and x['reduced_passed'] for x in rows),'rows':rows,'count':args.count,'scope':'one fixed grain and a force/torque-free particle; no gravity/contact; matrix applicability still requires checks','hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(mfs.__file__),Path(sphere.__file__),Path(reduced.__file__)]}}
    (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'rows':len(rows)}),flush=True)
if __name__=='__main__':main()
