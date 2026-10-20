"""Read-only geometry arithmetic diagnosis; no repaired gaps or trajectories."""
from pathlib import Path
from decimal import Decimal, localcontext
import os, traceback
import numpy as np
import authenticate_failed_system_v1 as source

job, api, ROOT, frozen = source.job, source.api, source.ROOT, source.frozen
OUT = ROOT / 'stage210_evaluations/three_contact_failure_20261001/sphere_gap_arithmetic_01'


def dec(x):
    return Decimal.from_float(float(x))


def norm(x):
    return sum(v*v for v in x).sqrt()


def run():
    d = api.read(job.DESIGN); job.verify(d)
    w = api.read(source.WORK); api.require(w['maximum_new_trajectory_steps'] == 0, 'zero steps')
    fp = source.OUT / 'failed_systems.json'; proof = api.read(source.OUT / 'results.json')
    api.require(api.sha(fp) == proof['failed_systems_sha256'], 'authenticated rejected equations')
    evidence = api.read(fp); trial = evidence['failed_outer_trials'][0]
    prodpath = job.RUN / w['case'] / 'result.json'
    api.require(api.read(prodpath.parent / 'completion.json')['result_sha256'] == api.sha(prodpath), 'producer seal')
    state = api.read(prodpath)['final_result']['checkpoint']['state']
    case = next(c for c in d['cases'] if c['id'] == w['case']); spec = case['spec']
    axes = spec['config']['prolate_semiaxes_m']; api.require(axes[0] == axes[1] == axes[2], 'exact sphere')
    geom = spec['field_metadata']['geometry']; gp = Path(geom['path'])
    api.require(api.sha(gp) == geom['sha256'], 'frozen grain geometry')
    srcpath = ROOT / 'stage37_staging/transport_contact.py'
    sys = __import__('sys'); sys.path.insert(0, str(srcpath.parent))
    import transport_contact as original
    api.require(api.sha(srcpath) == d['sources'][str(srcpath)], 'original geometry source')
    data = np.load(gp); centres = data['sand_centres_m']; radii = data['sand_radii_m']
    L = spec['field_metadata']['cell_length_m']; x = np.asarray(state['x']); p = np.asarray(state['p']); a = axes[0]
    api.require(state['q'] == trial['outer_inputs'][0] and a == trial['outer_inputs'][7], 'held rejected pose/velocity binding')
    inputs = {str(q): api.sha(q) for q in (source.WORK, job.DESIGN, Path(__file__), fp, prodpath, gp, srcpath)}
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT/'launch.json', dict(pid=os.getpid(), utc=job.utc().isoformat(), new_trajectory_steps=0, inputs=inputs))
    try:
        reports = []
        with localcontext() as ctx:
            ctx.prec = 100
            for grain, savedgap, savednormal, savedlever in trial['outer_inputs'][6]:
                centre = centres[grain]; radius = float(radii[grain])
                delta = centre-x; images = np.round(delta/L); delta -= L*images; imagecentre = x+delta
                gap, n, lever = original.ellipsoid_grain_contact(x,p,a,a,imagecentre,radius)
                api.require(gap == savedgap and np.array_equal(n,savednormal) and np.array_equal(lever,savedlever), 'exact saved contact reproduction')
                # Two independently defined exact quantities: original rounded image
                # centre, and exact periodic difference of binary64 input geometry.
                dc = [dec(c)-dec(xx) for c,xx in zip(imagecentre,x)]
                dd = [dec(c)-dec(xx)-dec(L)*dec(im) for c,xx,im in zip(centre,x,images)]
                exact_image_gap = norm(dc)-dec(a)-dec(radius)
                exact_periodic_gap = norm(dd)-dec(a)-dec(radius)
                stable_float_gap = float(np.linalg.norm(delta)-(a+radius))
                translated = []
                for shift in (np.array([L,0.,0.]), np.array([0.,0.,L]), np.array([10*L,-10*L,10*L])):
                    tg,_,_ = original.ellipsoid_grain_contact(x+shift,p,a,a,imagecentre+shift,radius)
                    translated.append(dict(shift_m=shift.tolist(), gap_m=tg, gap_change_m=tg-gap))
                scale = max(np.linalg.norm(evidence['failed_inner_systems'][0]['system']['vfree']),1e-15)
                dt = trial['outer_inputs'][8]; tolerance = evidence['failed_inner_systems'][0]['system']['tolerance']
                # This is a residual scale, not a replacement gap tolerance or gate.
                reports.append(dict(grain_id=grain, saved_original_gap_m=gap,
                    exact_binary64_rounded_image_gap_m=str(exact_image_gap), exact_binary64_periodic_gap_m=str(exact_periodic_gap),
                    original_minus_exact_image_gap_m=str(dec(gap)-exact_image_gap),
                    stable_float_sphere_formula_gap_m=stable_float_gap,
                    radial_normal_lever_cross_over_radius=np.cross(lever,n).__truediv__(a).tolist(),
                    original_relative_velocity_tolerance=tolerance,
                    dt_times_velocity_scale_times_relative_tolerance_m=dt*scale*tolerance,
                    translated_original_formula=translated))
        api.verify_mapping(inputs); job.verify(d)
        r = dict(geometry_evidence_reproduced=True,new_trajectory_steps=0, original_campaign_remains_failed=True,
                 original_gaps_not_changed=True, no_numerical_repair_installed=True, contacts=reports, inputs=inputs,
                 claim='Arithmetic sensitivity of saved sphere geometry only. Decimal sphere distances are diagnostic comparators, not admissible replacement gaps, acceptance criteria, or proof that every frictional mode is infeasible.')
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print(__import__('json').dumps(r,indent=2),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__ == '__main__': run()
