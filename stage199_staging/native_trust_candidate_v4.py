"""Original NumPy cube AND scalar square-root power, strict native control.

v3 is rejected: its scalar x**.5 expansion first changed bits at fine step2995.
Both power operations now retain NumPy rather than LLVM replacement rules.
"""
from contextlib import contextmanager
from types import SimpleNamespace
import ast,inspect
import numpy as np
import native_trust_candidate_v2 as previous
prior=previous.prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq
original_trust=previous.original_trust
phi,norm9=previous.phi,previous.norm9

@compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def scalar_power_half(x):
    with compiled.numba.objmode(answer='float64'):
        answer=np.float64(x)**.5
    return answer

tree=ast.parse(inspect.getsource(previous.trust9.py_func));changes=0
tree.body[0].decorator_list=[]
class Power(ast.NodeTransformer):
    def visit_BinOp(self,node):
        global changes
        if ast.unparse(node)=='(alpha_lower * alpha_upper) ** 0.5':
            changes+=1
            return ast.copy_location(ast.Call(func=ast.Name(id='scalar_power_half',ctx=ast.Load()),args=[node.left],keywords=[]),node)
        return self.generic_visit(node)
Power().visit(tree)
if changes!=2:raise RuntimeError('exactly two scalar power operations retained in NumPy')
ast.fix_missing_locations(tree);ns={**globals()}
exec(compile(tree,__file__,'exec'),ns)
trust9=compiled.numba.njit(ns['trust9'],cache=True,fastmath=False,parallel=False,error_model='numpy')

def trust(n,m,uf,s,V,Delta,initial_alpha=None,rtol=.01,max_iter=10):
    if n==m==9 and rtol==.01 and max_iter==10 and np.isfinite(Delta) and Delta>0 and all(type(x) is np.ndarray and x.dtype==np.float64 for x in (uf,s,V)) and uf.shape==s.shape==(9,) and V.shape==(9,9):
        return trust9(uf,s,V,Delta,initial_alpha,rtol,max_iter)
    return original_trust(n,m,uf,s,V,Delta,initial_alpha=initial_alpha,rtol=rtol,max_iter=max_iter)

trf_no_bounds=prior.clone(prior.trf_no_bounds,{'solve_lsq_trust_region':trust})
least_squares=prior.clone(prior.least_squares,{'trf':SimpleNamespace(trf_no_bounds=trf_no_bounds)})

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        with prior.scope('compiled_direct'):
            saved=repair.prior.least_squares;repair.prior.least_squares=least_squares
            try:yield
            finally:repair.prior.least_squares=saved
    else:raise ValueError('explicit benchmark mode required')
