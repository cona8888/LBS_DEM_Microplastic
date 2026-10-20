"""Strict fixed-size helper dispatch; original TRF decisions/controls retained."""
from types import SimpleNamespace
from contextlib import contextmanager
import ast,inspect
import numpy as np
import exact_solver_brackets_v1 as prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq
clone=prior.prior.prior.clone
original_norm=prior.prior.prior.norm
original_scale=prior.trf_no_bounds.__globals__['compute_jac_scale']

@compiled.numba.njit(cache=True,fastmath=False,parallel=False)
def all_finite(x):
    for i in range(x.size):
        if not np.isfinite(x.flat[i]):return False
    return True

@compiled.numba.njit(cache=True,fastmath=False,parallel=False)
def max_abs(x):
    v=0.
    for i in range(len(x)):
        z=abs(x[i])
        if np.isnan(z):return z
        if z>v:v=z
    return v

@compiled.numba.njit(cache=True,fastmath=False,parallel=False)
def column_norms(J):
    out=np.zeros(J.shape[1])
    for i in range(J.shape[0]):
        for j in range(J.shape[1]):out[j]+=J[i,j]*J[i,j]
    for j in range(J.shape[1]):out[j]=np.sqrt(out[j])
    return out

def norm(x,ord=None):
    if ord==np.inf and type(x) is np.ndarray and x.dtype==np.float64 and x.ndim==1:
        return max_abs(x)
    return original_norm(x,ord=ord)

def compute_jac_scale(J,scale_inv_old=None):
    if not (type(J) is np.ndarray and J.dtype==np.float64 and J.shape==(9,9) and J.flags.c_contiguous):return original_scale(J,scale_inv_old)
    scale_inv=column_norms(J)
    if scale_inv_old is None:scale_inv[scale_inv==0]=1
    else:scale_inv=np.maximum(scale_inv,scale_inv_old)
    return 1/scale_inv,scale_inv

trust_original=prior.trf_no_bounds.__globals__['solve_lsq_trust_region']
tree=ast.parse(inspect.getsource(trust_original));count=0
class Squares(ast.NodeTransformer):
    def visit_BinOp(self,node):
        global count
        if ast.unparse(node) in ('s ** 2','suf ** 2'):
            count+=1;return ast.copy_location(ast.Name(id='_s2' if ast.unparse(node)=='s ** 2' else '_suf2',ctx=ast.Load()),node)
        return self.generic_visit(node)
Squares().visit(tree)
outer=tree.body[0];index=next(i for i,v in enumerate(outer.body) if isinstance(v,ast.Assign) and ast.unparse(v.targets[0])=='suf')
outer.body[index+1:index+1]=ast.parse('_s2 = s**2\n_suf2 = suf**2').body
if count!=3:raise RuntimeError('exactly three invariant-square use replacements')
ast.fix_missing_locations(tree);ns={**trust_original.__globals__,'norm':norm}
exec(compile(tree,__file__+'::invariant_squares','exec'),ns);trust=ns['solve_lsq_trust_region']
tree=ast.parse(inspect.getsource(prior.trf_no_bounds));finite_changes=0
class Finite(ast.NodeTransformer):
    def visit_Call(self,node):
        global finite_changes
        if ast.unparse(node)=='np.all(np.isfinite(f_new))':
            finite_changes+=1;return ast.copy_location(ast.Call(func=ast.Name(id='_all_finite',ctx=ast.Load()),args=[ast.Name(id='f_new',ctx=ast.Load())],keywords=[]),node)
        return self.generic_visit(node)
Finite().visit(tree)
if finite_changes!=1:raise RuntimeError('exactly one unchanged finite-input decision specialization')
ast.fix_missing_locations(tree)
ns={**prior.trf_no_bounds.__globals__,'norm':norm,'compute_jac_scale':compute_jac_scale,'solve_lsq_trust_region':trust,'_all_finite':all_finite}
exec(compile(tree,__file__+'::fixed_shape_helpers','exec'),ns);trf_no_bounds=ns['trf_no_bounds']
least_squares=clone(prior.least_squares,{'trf':SimpleNamespace(trf_no_bounds=trf_no_bounds)})

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        saved=repair.prior.least_squares;repair.prior.least_squares=least_squares
        try:
            with compiled.scope(True),batch.scope():yield
        finally:repair.prior.least_squares=saved
    else:raise ValueError('explicit benchmark mode required')
