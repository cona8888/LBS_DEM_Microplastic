"""NumPy-BLAS compiled cold PGS, retaining Stage53's two original finite-difference LM paths.

No historical module is rebound. The original Stage50 physical gate is the
final authority. Work counters include failed LM attempts and cold PGS sweeps.
"""
import sys
import time
from pathlib import Path
import numpy as np
from scipy.optimize import root

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'stage50_staging'), str(ROOT/'stage53_staging')]
import inertial_contact_seeded_lm_v1 as original
import inertial_contact_multistart_lm_v1 as reference_stage53
from compiled_blas_loop import cold_loop


class CompiledStage53:
    def __init__(self):
        self.work = {'calls': 0, 'pgs_sweeps': 0, 'seeded_lm_nfev': 0,
                     'zero_lm_nfev': 0, 'failed_calls': 0, 'wall_seconds': 0.0,
                     'reference_disagreement_fallbacks': 0,
                     'reference_disagreement_wall_seconds': 0.0}

    def stats(self):
        return dict(self.work)

    def __call__(self, vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        started = time.perf_counter()
        self.work['calls'] += 1
        try:
            return self._solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
        except Exception:
            self.work['failed_calls'] += 1
            raise
        finally:
            self.work['wall_seconds'] += time.perf_counter()-started

    def _solve(self, vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        vfree = original.contact_model.finite(vfree)
        mobility = original.contact_model.finite(mobility)
        jacobian = original.contact_model.finite(jacobian)
        gaps = original.contact_model.finite(gaps)
        if (vfree.ndim != 1 or gaps.ndim != 1 or mobility.shape != (len(vfree),len(vfree))
                or jacobian.shape != (3*len(gaps),len(vfree))):
            raise ValueError('invalid compiled contact array shapes')
        if (not np.isfinite([dt, friction, tol]).all() or dt <= 0 or friction < 0
                or tol <= 0 or maxiter < 1 or int(maxiter) != maxiter):
            raise ValueError('invalid compiled contact controls')
        if not len(gaps):
            return vfree, {'iterations': 0, 'residual': 0., 'force_residual': 0.,
                           'dissipation': 0., 'reactions': [], 'solver': 'standard_cold_pgs'}
        A = jacobian @ mobility @ jacobian.T
        z = jacobian @ vfree
        scale = max(np.linalg.norm(vfree), 1e-15)
        if (not np.isfinite(A).all() or not np.isfinite(z).all() or not np.isfinite(scale)
                or A.dtype != np.float64 or z.dtype != np.float64
                or not A.flags.c_contiguous or not z.flags.c_contiguous):
            raise ValueError('nonfinite or unsupported compiled BLAS input layout')
        steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max()
                          for k in range(len(gaps))])
        if not np.isfinite(steps).all() or np.any(steps <= 0) or np.any(np.diag(A)[::3] <= 0):
            raise RuntimeError('nonpositive direct contact scale')
        force, sweeps, converged = cold_loop(A, z, gaps, dt, friction, steps,
                                             scale, tol, maxiter, 1.0)
        self.work['pgs_sweeps'] += int(sweeps)
        if converged:
            try:
                return self._finish(vfree, mobility, jacobian, force, z, A,
                    gaps, dt, friction, steps, int(sweeps), 'standard_cold_pgs', {})
            except RuntimeError as exc:
                if str(exc) != 'direct contact residual nonconvergence':
                    raise
                # A compiled threshold decision cannot skip the reference's
                # remaining PGS or seeded LM path. Re-run the untouched solver.
                self.work['reference_disagreement_fallbacks'] += 1
                started = time.perf_counter()
                try:
                    return self._checked(reference_stage53._solve(vfree,mobility,
                        jacobian,gaps,dt,friction,tol,maxiter))
                finally:
                    self.work['reference_disagreement_wall_seconds'] += time.perf_counter()-started
        if len(gaps) > 3:
            raise RuntimeError('contact nonconvergence; seeded LM contact limit exceeded')
        return self._lm(vfree, mobility, jacobian, gaps, dt, friction,
                        A, z, steps, scale, force, maxiter)

    @staticmethod
    def _checked(answer):
        velocity, health = answer
        if not np.isfinite(velocity).all() or not np.isfinite(health['reactions']).all():
            raise RuntimeError('nonfinite direct contact reaction')
        if not np.isfinite([health[k] for k in ('residual','force_residual','dissipation')]).all():
            raise RuntimeError('nonfinite direct contact health')
        return answer

    def _finish(self, *args):
        if not np.isfinite(args[3]).all():
            raise RuntimeError('nonfinite direct contact reaction')
        return self._checked(original._finish(*args))

    def _lm(self, vfree, mobility, jacobian, gaps, dt, friction, A, z, steps,
            scale, force, maxiter):
        scales = np.repeat(steps, 3)
        for k in range(len(gaps)):
            scales[3*k] = A[3*k,3*k]
        if np.any(scales <= 0) or not np.isfinite(scales).all():
            raise RuntimeError('nonpositive direct contact scale')
        if len(gaps) > 3:
            raise RuntimeError('zero-seeded LM contact limit exceeded')

        def equations(u):
            f = u/scales
            velocity = z+A@f
            result = np.empty_like(u)
            for k in range(len(gaps)):
                i = 3*k
                vn = velocity[i]+gaps[k]/dt
                result[i] = np.hypot(u[i],vn)-u[i]-vn
                result[i+1:i+3] = u[i+1:i+3]-steps[k]*original._project(
                    f[i+1:i+3],velocity[i+1:i+3],steps[k],friction*f[i])
            return result/scale

        solved = root(equations, force*scales, method='lm',
            options={'ftol':1e-14,'xtol':1e-14,'gtol':1e-14,'maxiter':50000})
        self.work['seeded_lm_nfev'] += int(solved.nfev)
        try:
            return self._finish(vfree,mobility,jacobian,solved.x/scales,z,A,
                gaps,dt,friction,steps,maxiter+int(solved.nfev),
                'cold_pgs_seeded_scaled_lm',{'pgs_seed_iterations':maxiter,
                'lm_nfev':int(solved.nfev),'lm_success_flag':bool(solved.success),
                'lm_message':str(solved.message)})
        except RuntimeError as exc:
            if str(exc) != 'direct contact residual nonconvergence':
                raise
        solved = root(equations, np.zeros(len(z)), method='lm',
            options={'ftol':1e-14,'xtol':1e-14,'gtol':1e-14,'maxiter':50000})
        self.work['zero_lm_nfev'] += int(solved.nfev)
        return self._finish(vfree,mobility,jacobian,solved.x/scales,z,A,
            gaps,dt,friction,steps,maxiter+int(solved.nfev),
            'cold_pgs_then_zero_seeded_scaled_lm',{'pgs_seed_iterations':maxiter,
            'zero_lm_nfev':int(solved.nfev),'zero_lm_success_flag':bool(solved.success),
            'zero_lm_message':str(solved.message)})
