"""Non-advancing first-iteration matrix diagnostic at four step sizes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage139_staging'))
import sphere_only_verification_v1 as parent
api,engine,hot,fast=parent.api,parent.engine,parent.hot,parent.fast
OUT=ROOT/'stage141_evaluations/fibre_identical_system_branch_check_20260918/sphere_step_scale_probe_01'

def main():
    pd=api.read(parent.DESIGN);parent.verify(pd)
    c=next(c for c in pd['cases'] if c['id']=='sphere_12_terminal');spec=c['spec'];cfg=spec['config']
    source=api.read(c['source'])['result'];a,b,_=cfg['prolate_semiaxes_m'];np=api.np
    x,p,q=map(np.array,(source['position_m'],source['orientation'],source['velocity_generalized']))
    api.require(source['checkpoint']['state_sha256']==api.digest(source['checkpoint']['state']),'source state')
    parent.old.prior.prior.configure();field,data,metadata=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    api.require(metadata==spec['field_metadata'],'field binding')
    geom=api.frozen.h.geometry_exact_v1.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],metadata['cell_length_m'])
    core=engine.runtime.core;mechanics=core.mechanics;inertial=hot.s50.s42
    mu=cfg['dynamic_viscosity_Pa_s'];rhop=cfg['particle_density_kg_m3'];rhof=cfg['fluid_density_kg_m3']
    u,grad=field.sample(x);background,_=mechanics.free_motion(p,grad,u,a,b,mu,1.,1.,[0,0,0])
    stokes=inertial.stokes_generalized_resistance(p,a,b,mu)
    mass,_=inertial.generalized_mass_matrix(p,a,b,rhop,rhof,cfg['added_mass_fraction']);mass[3:,3:]=0.
    body=np.r_[(rhop-rhof)*4*np.pi*a*b*b/3*np.array(cfg['gravity_m_s2']),np.zeros(3)]
    near=core.enrich(geom,geom.contacts(x,p,a,b,.2*max(geom.r)))
    lubrication,_=core.lubrication_matrix(near,p,a,b,a,mu,.2,.01)
    translation=max(np.linalg.norm(q[:3]),np.linalg.norm(background[:3]),np.linalg.norm(body[:3])/np.linalg.eigvalsh(stokes[:3,:3]).min(),1e-30)
    rotation=max(np.linalg.norm(q[3:]),np.linalg.norm(background[3:]),1e-30)/a
    n=cfg['numerics'];dt0=min(n['max_dt_s'],n['displacement_fraction']*b/translation,n['angle_limit_rad']/rotation,n['relaxation_fraction']*np.linalg.eigvalsh(mass[:3,:3]).min()/np.linalg.eigvalsh(stokes[:3,:3]).max())
    tests=[('original_step',dt0),('half_step',dt0/2),('quarter_step',dt0/4),('reported_endpoint_remainder',8.213588595706867e-6)]
    OUT.mkdir(parents=True,exist_ok=False)
    protocol={'question':'Does roundoff-scale signed gap divided by a smaller dt exclude the fast all-stick candidate?',
              'source':c['source'],'source_sha256':api.sha(c['source']),'source_code_sha256':api.sha(__file__),
              'parent_design_sha256':api.sha(parent.DESIGN),'tests':tests,'claim':'First fixed-point matrix diagnostic only; no trajectory or time advanced. The zero-gap control is synthetic and is never used for production.'}
    api.write(OUT/'protocol.json',protocol)
    rows=[];deq=2*(a*b*b)**(1/3)
    re=inertial.finite_re.reynolds_number(q[:3]-background[:3],rhof,mu,deq)
    factor=inertial.finite_re.inertial_multiplier(re,inertial.finite_re.prolate_sphericity(a,b))
    drag=stokes.copy();drag[:3,:3]*=factor
    for label,dt in tests:
        contacts=geom.contacts(x,p,a,b,(translation+a*rotation)*dt+1e-5*b)
        J,g,_=hot.s50.s41._prepare_geometry(contacts,a)
        M=np.linalg.inv(mass/dt+drag+lubrication);v=M@(mass@q/dt+drag@background+body)
        for gap_mode,gg in [('original_signed_gaps',g),('synthetic_zero_gap_control',np.zeros_like(g))]:
            target=np.zeros(len(J));target[::3]=-gg/dt;qs=np.linalg.lstsq(J,target,rcond=1e-12)[0]
            residual=float(np.max(np.abs(J@qs-target))/max(np.linalg.norm(v),1e-15))
            row={'test':label,'gap_mode':gap_mode,'dt_s':dt,'gaps_m':gg.tolist(),'constraint_residual_scaled':residual}
            try:
                answer,h=parent.old.prior.scalar_scope._scoped(fast.candidate,v,M,J,gg,dt,.3,1e-10,25000)
                row.update(candidate_returned=True,health=h,independent=engine.local.independent_contact(v,M,J,gg,dt,.3,answer,h))
            except (ValueError,RuntimeError) as exc:row.update(candidate_returned=False,error=str(exc))
            rows.append(row)
    parent.verify(pd)
    api.write(OUT/'results.json',{'rows':rows,'protocol_sha256':api.sha(OUT/'protocol.json'),'claim':protocol['claim']})
    api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print([{k:r[k] for k in ['test','gap_mode','dt_s','constraint_residual_scaled','candidate_returned']} for r in rows],flush=True)

if __name__=='__main__':main()
