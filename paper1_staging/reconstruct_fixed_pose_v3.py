"""Extract original assembly statements for zero-advancement saved-pose diagnosis."""
from pathlib import Path
import ast
import copy
import json
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_core_v2 as shared
s = shared.s
model = s.q.job.parent.model.original
import modal_rotation_dt_v1 as modal


def build():
    source = ast.parse(modal.GENERATED_SOURCE).body[0]
    loop = next(n for n in source.body if isinstance(n, ast.Try)).body[0]
    s.require(isinstance(loop, ast.While), 'Original integration-loop structure')
    names = {'tolerance', 'equivalent_diameter', 'sphericity', 'maximum_grain_radius'}
    constants = [copy.deepcopy(n) for n in source.body if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names]
    s.require(len(constants) == 4, 'Original four geometry/physical constants')
    start = next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Assign)
                 and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'initial')
    stop = next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Assign)
                and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'accepted')
    attempt = next(n for n in loop.body if isinstance(n,ast.For))
    preparation = [copy.deepcopy(n) for n in attempt.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('reach','active')]
    s.require([ast.unparse(n.targets[0]) for n in preparation] == ['reach','active'], 'Original contact-membership operands')
    call = next(n for n in ast.walk(attempt) if isinstance(n,ast.Call)
                and isinstance(n.func,ast.Attribute) and n.func.attr == 'inertial_contact_step')
    signature = ('field,geometry,x,p,q,a,b,viscosity,particle_density,fluid_density,gravity,friction,'
                 'horizon,t,added_mass_fraction,cutoff_ratio,roughness_ratio,displacement_fraction,'
                 'angle_limit,relaxation_fraction,max_dt,reynolds_limit,rigid_rotation=True,max_reynolds=0.')
    tree = ast.parse('def assemble('+signature+'):\n    pass\n')
    fn = tree.body[0]
    fn.body = constants + copy.deepcopy(loop.body[start:stop]) + preparation + [ast.Return(ast.Tuple(copy.deepcopy(call.args),ast.Load()))]
    # These are original statements before the contact solve; no solver,
    # advancement, history update, event or checkpoint code is copied.
    forbidden = {'inertial_contact_step','advance_pose','snapshot','record_dwell'}
    s.require(not any(isinstance(n,ast.Call) and (getattr(n.func,'attr','') in forbidden
                  or getattr(n.func,'id','') in forbidden) for n in ast.walk(tree)), 'No numerical advancement or solve')
    ast.fix_missing_locations(tree); namespace = dict(modal.CANDIDATE.__globals__)
    exec(compile(tree, str(Path(__file__).resolve())+'::original_assembly_only','exec'),namespace)
    return namespace['assemble'], ast.unparse(tree)


ASSEMBLE, EXTRACTED_SOURCE = build()


def inspect_one(name='p1_i0_fibre_u0p5_fine_20261014', label='production_00302', index=10, include_fixture=False):
    root=s.ROOT/'paper1_runs'/name; design=s.ROOT/'paper1_designs'/name/'physical_cases_01.json'
    retired=s.fields.sealed(root/'retirement_01/results.json'); raw=root/'records'/label/'call.json.xz'
    s.require(retired['passed'] and retired['artifacts'][str(raw)]==s.sha(raw), 'Retired complete raw ancestry binds this record')
    codec=shared.archives.build(s.q.job.codec,preset=9)
    wire=json.loads(codec.base.read_bytes(raw,s.sha(design)))['packed_envelope']['payload']
    spec=wire['spec']; cfg=spec['config']; prev=wire['rows'][index-1]; wanted=wire['rows'][index]
    case,field,data=s.factory.load_case('p1_i0_rigid_prolate_ar4_u0p5',.01,s.read(design)['cases'][0]['factor'],'core')
    s.require(case['spec']==spec, 'Exact saved physical case, field and numerical controls')
    geometry=s.api.frozen.h.geometry_exact_v1.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],spec['field_metadata']['cell_length_m'])
    a,b,_=cfg['prolate_semiaxes_m']; n=cfg['numerics']
    args=ASSEMBLE(field,geometry,np.asarray(prev['position_m']),np.asarray(prev['orientation']),
        np.asarray(prev['velocity_generalized']),a,b,cfg['dynamic_viscosity_Pa_s'],cfg['particle_density_kg_m3'],
        cfg['fluid_density_kg_m3'],cfg['gravity_m_s2'],cfg['friction_coefficient'],spec['horizon_s'],prev['time_s'],
        cfg['added_mass_fraction'],.2,.01,n['displacement_fraction'],n['angle_limit_rad'],n['relaxation_fraction'],
        n['max_dt_s'],n['reynolds_limit'])
    prepare=wire['normal_gap_operand_policy']['prepare_calls'][index]
    def plain(x):
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,(tuple,list)):return [plain(v) for v in x]
        if isinstance(x,np.generic):return x.item()
        return x
    got=plain(args[6]); expected=prepare['contacts']
    report = dict(root=name,label=label,index=index,new_transport_steps=0,contact_solve_calls=0,
        dt_exact=float(args[8])==wire['sweep_certificates'][index]['dt_s'],
        assembled_dt_s=float(args[8]),saved_solver_dt_s=wire['sweep_certificates'][index]['dt_s'],
        saved_row_interval_dt_s=wanted['dt_s'],contacts_exact=got==expected,
        assembled_contacts=got,saved_contacts=expected,
        maximum_contact_operand_absolute_difference=max((float(np.max(np.abs(np.ravel(np.asarray(g[1],float))-np.ravel(np.asarray(e[1],float))))) for g,e in zip(got,expected)),default=0.),
        original_assembly_source_sha256=s.api.digest(EXTRACTED_SOURCE))
    if include_fixture:
        return dict(report=report,outer_arguments=plain(args),
            expected_first_inner=wire['contact_trial_trace']['cycle_guard_trials'][index]['records'][0],
            expected_accepted_velocity=wanted['velocity_generalized'],
            speed_m_s=cfg['target_mean_interstitial_velocity_m_s'],
            inputs={str(raw):s.sha(raw),str(design):s.sha(design),
                    str(root/'retirement_01/results.json'):s.sha(root/'retirement_01/results.json')})
    return report


if __name__ == '__main__':
    print(json.dumps(inspect_one()),flush=True)
