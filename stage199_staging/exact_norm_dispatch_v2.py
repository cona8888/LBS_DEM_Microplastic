"""Keep dynamically instrumented outer solve live; narrow norm clones only."""
from contextlib import contextmanager
import exact_norm_dispatch_v1 as previous
ROOT,repair,compiled,batch=previous.ROOT,previous.repair,previous.compiled,previous.batch
constant,lsq=previous.constant,previous.lsq
trf_no_bounds,least_squares=previous.trf_no_bounds,previous.least_squares
original_norm,norm,clone=previous.original_norm,previous.norm,previous.clone
prior=previous.prior

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        with prior.scope('compiled_direct'):
            fast=batch.original
            targets=[(fast,'scalar_solve'),(fast,'solve'),(fast.old,'constrained_stick'),(fast.gate,'_finish'),(fast.gate,'_residual')]
            saved=[]
            try:
                for module,name in targets:
                    fn=getattr(module,name);saved.append((module,name,fn));setattr(module,name,clone(fn))
                system=repair.prior.analytic.system;saved.append((repair.prior.analytic,'system',system));repair.prior.analytic.system=clone(system)
                yield
            finally:
                for module,name,fn in reversed(saved):setattr(module,name,fn)
    else:raise ValueError('explicit benchmark mode required')
