"""Scoped solver-operand policy: raw geometry/contact membership never changes."""
from contextlib import contextmanager
from pathlib import Path
import copy,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage212_staging'))
import roundoff_sphere_gap_v1 as policy
import close_roundoff_gap_v1 as proof
job,api=proof.job,proof.api
model=job.fast.gate.contact_model
backend=job.observer.backend.stage41
sys.path.insert(0,str(ROOT/'stage41_staging'))
import geometry_exact_v1 as exact_geometry
NAME='stage213_normal_solver_gap_operand_scope_v1'

def plain_contacts(contacts):
    return [[int(k),float(g),np.asarray(n).tolist(),np.asarray(l).tolist()] for k,g,n,l in contacts]

@contextmanager
def scope(maximum_prepare_calls=10001):
    classes=(model.GrainGeometry,exact_geometry.GrainGeometry)
    original_methods={cls:cls.contacts for cls in classes};original_prepare=backend._prepare_geometry
    contexts={};log=dict(policy=policy.NAME,scope=NAME,raw_geometry_membership_lubrication_sweep_dwell_unchanged=True,prepare_calls=[])
    def method(original):
        def contacts(geom,x,p,a,b,skin=0.):
            result=original(geom,x,p,a,b,skin)
            for k,g,n,l in result:
                delta=geom.c[k]-x;delta-=geom.L*np.round(delta/geom.L);c=np.asarray(x)+delta
                context=dict(grain_id=int(k),x=np.asarray(x).tolist(),p=np.asarray(p).tolist(),a=float(a),b=float(b),
                             c=c.tolist(),r=float(geom.r[k]),raw_gap_m=float(g),normal=np.asarray(n).tolist(),lever=np.asarray(l).tolist(),
                             original_skin_m=float(skin),original_periodic_length_m=float(geom.L))
                contexts[id(n)]=(n,context)
            return result
        return contacts
    def prepare(contacts,ell):
        J,g,frames=original_prepare(contacts,ell)
        api.require(len(log['prepare_calls'])<maximum_prepare_calls,'bounded complete operand provenance')
        effective=g.copy();meta=[]
        for index,(k,raw,n,l) in enumerate(contacts):
            api.require(id(n) in contexts and contexts[id(n)][0] is n,'exact live raw geometry provenance')
            context=contexts[id(n)][1]
            api.require(context['grain_id']==int(k) and context['raw_gap_m']==raw
                        and context['normal']==np.asarray(n).tolist() and context['lever']==np.asarray(l).tolist(),'raw contact context binding')
            value,m=policy.classify(context['x'],context['c'],context['a'],context['b'],context['r'],raw)
            effective[index]=value;meta.append(dict(context=copy.deepcopy(context),classification=m))
        log['prepare_calls'].append(dict(index=len(log['prepare_calls']),contacts=plain_contacts(contacts),ell_m=float(ell),
                                       jacobian_sha256=api.digest(J.tolist()),raw_gaps_m=g.tolist(),effective_gaps_m=effective.tolist(),metadata=meta))
        return J,effective,frames
    for cls,original in original_methods.items():cls.contacts=method(original)
    backend._prepare_geometry=prepare
    try:yield log
    finally:
        backend._prepare_geometry=original_prepare
        for cls,original in original_methods.items():cls.contacts=original

