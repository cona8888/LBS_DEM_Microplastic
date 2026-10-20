"""Original scalar scan with strict compiled E/valid assembly only.

Grids, brackets, Brent iterations, matrix products, determinants, least
squares, ranks and physical gates retain their original Python/NumPy code.
"""
from pathlib import Path
from contextlib import contextmanager
import ast,inspect,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage194_staging'),str(ROOT/'stage196_staging')]
import compiled_analytic_pair_v3 as compiled
import reduced_contact_fast_v1 as original
import numpy as np

@compiled.numba.njit(cache=True,fastmath=False,parallel=False)
def equation_arrays(w,stick,mu):
    E=np.zeros((len(w),9,5));valid=np.ones(len(w),dtype=np.bool_);col=0
    for k in range(3):
        if k==stick:
            for j in range(3):
                for i in range(len(w)):E[i,3*k+j,col]=1.
                col+=1
        else:
            for i in range(len(w)):
                x=w[i,3*k+1];y=w[i,3*k+2];speed=np.sqrt(x*x+y*y)
                positive=speed>0;valid[i]=valid[i] and positive;denom=speed if positive else 1.
                E[i,3*k,col]=1.;E[i,3*k+1,col]=(-mu*x)/denom;E[i,3*k+2,col]=(-mu*y)/denom
            col+=1
    return E,valid

tree=ast.parse(inspect.getsource(original.scalar_solve));changes=0
for node in ast.walk(tree):
    if isinstance(node,ast.FunctionDef) and node.name=='batch':
        positions=[i for i,v in enumerate(node.body) if isinstance(v,ast.Assign) and ast.unparse(v.targets[0]) in ('E','col','valid')]
        if len(positions)!=3 or positions!=list(range(positions[0],positions[0]+3)) or not isinstance(node.body[positions[-1]+1],ast.For):raise RuntimeError('original batch-array structure changed')
        start=positions[0];node.body[start:start+4]=ast.parse('E, valid = _equation_arrays(w, stick, mu)').body;changes+=1
if changes!=1:raise RuntimeError('one batch array assembly replacement required')
ast.fix_missing_locations(tree)
namespace={**original.__dict__,'_equation_arrays':equation_arrays}
exec(compile(tree,__file__+'::arrays_only','exec'),namespace)
scalar_solve=namespace['scalar_solve']

@contextmanager
def scope():
    before=original.scalar_solve;original.scalar_solve=scalar_solve
    try:yield
    finally:original.scalar_solve=before
