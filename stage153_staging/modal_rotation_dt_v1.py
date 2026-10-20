"""Use paired rotational relaxation modes; retain equations and all other caps.

For SPD mass M and Stokes resistance R, the decay times of M*q'= -R*q
are generalized eigenvalues of M*x=tau*R*x. A Cholesky congruence gives
the symmetric matrix L_R^-1*M*L_R^-T. This avoids pairing eigenvalues
from unrelated axes. It is not a general contact-stability certificate.
"""
import ast
from contextlib import contextmanager
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage152_staging'))
import complete_fibre_refinement_v1 as previous
model=previous.model
api=previous.api


def shortest_mode(mass,resistance):
    M=np.asarray(mass,float);R=np.asarray(resistance,float)
    if M.shape!=(3,3) or R.shape!=(3,3) or not np.isfinite(M).all() or not np.isfinite(R).all():
        raise ValueError('finite 3x3 rotational matrices required')
    for A in (M,R):
        if not np.allclose(A,A.T,rtol=0,atol=1e-12*np.linalg.norm(A)):
            raise ValueError('symmetric rotational matrices required')
    np.linalg.cholesky(M)
    L=np.linalg.cholesky(R)
    X=np.linalg.solve(L,M)
    H=np.linalg.solve(L,X.T).T
    value=float(np.linalg.eigvalsh((H+H.T)/2)[0])
    if not np.isfinite(value) or value<=0:raise ValueError('positive rotational decay time required')
    return value


def compile_candidate():
    tree=ast.parse(model.original.GENERATED_SOURCE);changed=0
    class Change(ast.NodeTransformer):
        def visit_Assign(self,node):
            nonlocal changed
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='tau_rot':
                changed+=1
                return ast.parse('tau_rot = shortest_mode(mass[3:,3:],resistance[3:,3:])').body[0]
            return self.generic_visit(node)
    Change().visit(tree)
    if changed!=1:raise RuntimeError('rotation timestep source structure changed')
    ast.fix_missing_locations(tree)
    ns=dict(model.original.INTEGRATE.__globals__);ns['shortest_mode']=shortest_mode
    exec(compile(tree,'<Stage153:paired_rotational_mode_dt>','exec'),ns)
    return ns['integrate'],ast.unparse(tree)


CANDIDATE,GENERATED_SOURCE=compile_candidate()


@contextmanager
def scope(enabled=True):
    if type(enabled) is not bool:raise ValueError('explicit bool required')
    saved=model.original.INTEGRATE
    if enabled:model.original.INTEGRATE=CANDIDATE
    try:
        with model.scope(True):yield
    finally:model.original.INTEGRATE=saved
