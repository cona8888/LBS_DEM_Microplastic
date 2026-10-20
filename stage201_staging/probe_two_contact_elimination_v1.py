"""Zero-step candidate: eliminate linear force/kinematic constraints first.

Rank-deficient two-contact force maps retain their nullspace. Unactuated body
directions enforce force compatibility, not an invented contact constraint.
Every proposed force still faces the unchanged original physical finalizer.
"""
from itertools import product
from pathlib import Path
import os
import time
import traceback
import numpy as np
from scipy.optimize import least_squares
import diagnose_two_contact_v1 as prior

job, api, source, ROOT = prior.job, prior.api, prior.source, prior.ROOT
OUT = ROOT / 'stage201_evaluations/contact_repair_20260928/two_contact_elimination_01'


def candidates(system, nearby, stop):
    v, M, J, g = [np.asarray(system[k], float) for k in ('vfree', 'mobility', 'jacobian', 'gaps_m')]
    dt, mu = system['dt_s'], system['friction']
    api.require(J.shape == (6, 6) and len(g) == 2, 'two contacts only')
    B = np.linalg.inv(M); load = B @ v
    fs = max(np.linalg.norm(load), 1e-30); vs = max(np.linalg.norm(v), 1e-15)
    qs = max(np.max(np.abs(g/dt)), vs*1e-12)
    A, z = J @ M @ J.T, J @ v
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(2)])
    gate = job.fast.gate; reports = []
    modes = sorted(product(range(3), repeat=2), key=lambda mode: (-sum(x == 1 for x in mode), sum(x == 0 for x in mode), mode))
    for mode in modes:
        api.require(time.time() < stop, 'work cutoff')
        active = [k for k in range(2) if mode[k]]
        fi = [3*k+j for k in active for j in range(3)]
        JT = J.T[:, fi]
        U, singular, Vh = np.linalg.svd(JT, full_matrices=True)
        rank = int(np.sum(singular > singular[0]*1e-12)) if len(singular) else 0
        P = (Vh[:rank].T / singular[:rank]) @ U[:, :rank].T
        Z = Vh[rank:].T
        E = U[:, rank:]
        constraints, target = [], []
        for k in active:
            constraints.append(J[3*k]); target.append(-g[k]/dt/qs)
            if mode[k] == 1:
                constraints.extend(J[3*k+1:3*k+3]); target.extend([0., 0.])
        # All body-force directions absent from the active contact map must
        # retain their original prescribed free dynamics.
        compatibility = E.T @ B
        right = E.T @ load / qs
        for row, rhs in zip(compatibility, right):
            norm = np.linalg.norm(row)
            constraints.append(row/norm); target.append(rhs/norm)
        C, target = np.asarray(constraints), np.asarray(target)
        cu, cs, cvh = np.linalg.svd(C, full_matrices=True)
        cr = int(np.sum(cs > cs[0]*1e-12))
        q0 = cvh[:cr].T @ ((cu[:, :cr].T @ target) / cs[:cr])
        N = cvh[cr:].T
        mismatch = float(np.max(np.abs(C@q0-target)))
        if mismatch > 1e-10*max(np.max(np.abs(target)), 1e-15):
            reports.append({'mode': list(mode), 'compatible': False, 'mismatch': mismatch}); continue
        width = N.shape[1]
        f0 = np.zeros(6); f0[fi] = P @ (B @ (q0*qs)-load) / fs
        D = np.zeros((6, width+Z.shape[1])); D[np.ix_(fi, range(width))] = P @ B @ N * qs/fs
        D[np.ix_(fi, range(width, width+Z.shape[1]))] = Z
        Q = np.column_stack((N, np.zeros((6, Z.shape[1]))))
        cq0, QD = J @ q0, J @ Q
        sliding = [k for k in active if mode[k] == 2]
        def both(y):
            f, vc = f0+D@y, cq0+QD@y
            residual, jac = [], []
            for k in sliding:
                i = 3*k; vt = vc[i+1:i+3]; speed = np.linalg.norm(vt)
                if speed < 1e-30:
                    direction = np.zeros(2); derivative = np.zeros((2, len(y)))
                else:
                    direction = vt/speed
                    derivative = (np.eye(2)-np.outer(direction, direction)) @ QD[i+1:i+3] / speed
                residual.extend(f[i+1:i+3]+mu*f[i]*direction)
                jac.extend(D[i+1:i+3]+mu*(np.outer(direction, D[i])+f[i]*derivative))
            return np.asarray(residual), np.asarray(jac)
        seeds = [np.zeros(width), np.ones(width), -np.ones(width)]
        for force in nearby[:3]:
            qnear = v+M@J.T@force
            seeds.append(N.T@(qnear/qs-q0))
        outputs = []
        for seed_index, seedq in enumerate(seeds):
            api.require(time.time() < stop, 'work cutoff')
            near = nearby[0] if nearby else np.zeros(6)
            eta = Z.T @ (near[fi]/fs-f0[fi]-D[np.ix_(fi, range(width))]@seedq)
            initial = np.r_[seedq, eta]
            if sliding and len(initial):
                opt = least_squares(lambda y: both(y)[0], initial, jac=lambda y: both(y)[1], xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=2000, x_scale='jac')
                y, nfev, cost = opt.x, int(opt.nfev), float(opt.cost)
            else:
                y, nfev, cost = initial, 0, 0.
            f = (f0+D@y)*fs
            entry = {'seed': seed_index, 'force': f.tolist(), 'nfev': nfev, 'cost': cost, 'residual': float(gate._residual(f,z,A,g,dt,mu,steps)/vs)}
            try:
                answer = gate._finish(v,M,J,f,z,A,g,dt,mu,steps,nfev,'stage201_held_eliminated_two_contact',{'contact_modes':list(mode),'force_map_rank':rank})
            except RuntimeError as error:
                entry.update(accepted=False, error=str(error))
            else:
                entry.update(accepted=True, velocity=answer[0].tolist(), health=answer[1])
            outputs.append(entry)
            if entry['accepted']:
                break
        reports.append({'mode':list(mode),'compatible':True,'force_map_rank':rank,'velocity_width':width,'force_nullspace_width':Z.shape[1],'candidates':outputs})
        if any(x['accepted'] for x in outputs):
            break
    return reports


def run():
    work = api.read(source.WORK); stop = job.policy.utc(work['work_end_utc']).timestamp()
    api.require(time.time()<stop, 'work window'); d=api.read(job.DESIGN); job.verify(d)
    source_path=source.OUT/'failed_systems.json'; prior_path=prior.OUT/'results.json'
    api.require(api.read(prior.OUT/'completion.json')['results_sha256']==api.sha(prior_path),'prior seal')
    bound=api.read(source_path)['failed_inner_systems']; previous=api.read(prior_path)['systems']
    OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (source.WORK,Path(__file__),source_path,prior_path,job.DESIGN)}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_modes_per_system':9,'maximum_seeds_per_mode':6,'maximum_nfev_per_call':2000})
    reports=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(bound):
                api.require(time.time()<stop,'work cutoff'); api.require(item['system_sha256']==previous[index]['input_sha256'],'same captured system')
                near=[np.asarray(x['force']) for x in sorted(previous[index]['baseline_candidates']+previous[index]['probes'],key=lambda x:x['residual'])[:3]]
                start=time.perf_counter(); modes=candidates(item['system'],near,stop)
                passed=any(c['accepted'] for m in modes for c in m.get('candidates',[]))
                row={'index':index,'input_sha256':item['system_sha256'],'passed':passed,'modes':modes,'seconds':time.perf_counter()-start}
                reports.append(row);job.commit(OUT/('system_%02d.json'%index),row)
                print('ELIMINATED',index,passed,flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result={'new_trajectory_steps':0,'inputs':inputs,'systems':reports,'accepted_systems':sum(r['passed'] for r in reports),'original_gates_unchanged':True,'claim':'Held-system candidate only, not a trajectory repair or production qualification.'}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
        print('ELIMINATION_COMPLETE',result['accepted_systems'],'/',len(reports),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'completed_systems':len(reports)});raise


if __name__=='__main__':run()
