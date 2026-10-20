"""Independent geometry and safety-contract checks before the cost-only GPU pilot."""
import numpy as np
import spatial_cost_v1 as job


def membership(zyx, n, centres, radii, length):
    xyz = (np.asarray(zyx)[:, ::-1]+.5) * length/n
    delta = xyz[:,None,:] - centres[None,:,:]
    delta -= length*np.rint(delta/length)
    return np.any(np.sum(delta**2,axis=2) <= radii[None,:]**2, axis=1)


def main():
    d = job.read(job.DESIGN)
    job.verify(d)
    with np.load(d['geometry']['path']) as data:
        phase, centres, radii = data['phase'], data['sand_centres_m'], data['sand_radii_m']
        length = float(data['cell_length_m'][0])
    with np.load(d['bindings']['source_geometry']['path']) as old:
        base = old['phase']; old_centres = old['sand_centres_m']; old_radii = old['sand_radii_m']
    reproduced = np.zeros(base.shape, dtype=bool)
    job.geom.mark_spheres(reproduced, centres, radii, length)
    rng = np.random.default_rng(125)
    nodes = rng.integers(0,279,size=(4096,3))
    # Explicit face/edge/corner samples in addition to volume samples.
    faces = rng.integers(0,279,size=(1536,3))
    for i in range(6): faces[i*256:(i+1)*256,i//2] = (0,278)[i%2]
    nodes = np.vstack((nodes,faces,np.array(np.meshgrid([0,278],[0,278],[0,278])).reshape(3,-1).T))
    exact = membership(nodes,279,centres,radii,length)
    observed = phase[tuple(nodes.T)] != 0
    connectivity = job.geom.connectivity(phase != 0)
    toy_centres = np.array([[.98,.03,.5]])
    toy_radii = np.array([.12])
    toy = np.zeros((13,)*3,dtype=bool)
    job.geom.mark_spheres(toy,toy_centres,toy_radii,1.)
    all_nodes = np.array(np.unravel_index(np.arange(13**3),(13,)*3)).T
    gpu, ram = job.gpu_snapshot(), job.available_ram()
    checks = {
        'source_grains_exact': np.array_equal(centres,old_centres) and np.array_equal(radii,old_radii),
        'cpd4_mask_exact_reproduction': np.array_equal(base != 0,reproduced),
        'independent_cpd6_volume_and_periodic_samples': np.array_equal(exact,observed),
        'independent_periodic_toy_exhaustive': np.array_equal(toy.ravel(),membership(all_nodes,13,toy_centres,toy_radii,1.)),
        'phase_hash': job.digest_array(phase)==d['geometry']['phase_array_sha256'],
        'binary_phase_and_dimensions': phase.shape==(279,)*3 and set(np.unique(phase))=={0,2},
        'finite_physical_grains': np.isfinite(centres).all() and np.isfinite(radii).all() and (radii>0).all() and len(radii)==216,
        'largest_fluid_component_over_99_percent': connectivity['largest_fluid_component_fraction']>=.99,
        'nonperiodic_spans_all_axes': all(connectivity['largest_component_spans_xyz_nonperiodic']),
        'allocation_formula_exact': d['cost_model']['device_bytes']==2*19*phase.size*4+phase.nbytes+4,
        'gpu_free_plus_reserve': gpu['free_bytes']>=d['cost_model']['device_bytes']+d['pilot']['gpu_reserve_bytes'],
        'host_ram_reserve': ram['available_bytes']>=d['pilot']['minimum_available_ram_bytes'],
        'gpu_temperature': gpu['temperature_C']<=d['pilot']['maximum_start_temperature_C'],
        'fixed_bounded_step_count': d['pilot']['warmup_steps']+d['pilot']['timed_blocks']*d['pilot']['steps_per_block']+1==d['pilot']['steps'],
        'no_prediction_authority': all(d['authority'][x] is False for x in ['full_steady_solve','transport','population','empirical_validation'])}
    result = {'passed': all(checks.values()), 'checks': {k:bool(v) for k,v in checks.items()},
              'design': job.bind(job.DESIGN), 'independent_geometry_samples': len(nodes),
              'connectivity': connectivity, 'gpu':gpu, 'ram':ram,
              'pilot_authorized': all(checks.values()), 'full_steady_solve_authorized':False}
    job.PREFLIGHT.parent.mkdir(parents=True,exist_ok=False)
    job.write(job.PREFLIGHT,result)
    job.write(job.PREFLIGHT.with_name('completion.json'),{'passed':result['passed'],'results_sha256':job.sha(job.PREFLIGHT)})
    print(result['checks'],flush=True)
    job.require(result['passed'],'preflight failed; no GPU launch')


if __name__ == '__main__': main()
