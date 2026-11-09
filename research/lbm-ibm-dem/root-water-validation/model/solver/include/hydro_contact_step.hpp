#pragma once

#include "ibm.hpp"
#include "wet_stepper.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <sstream>
#include <stdexcept>
#include <utility>
#include <vector>

namespace ibdem {

struct HydroContactControls {
    double relative_tolerance=1e-7, absolute_tolerance=1e-12, relaxation=1.0;
    int max_iterations=30;
};

struct HydroContactStepStats {
    WetParticleStats particles; // Accepted trajectory only: rejected trials do not count as contacts/work.
    int outer_iterations=0, ibm_iterations=0, ibm_rebuilds=0; // IBM work includes all outer trials.
    double residual_velocity=0.0, tolerance_velocity=0.0, periodic_angular_flux=0.0;
    double fluid_seconds=0.0, particle_seconds=0.0, coupling_seconds=0.0;
    std::vector<HydrodynamicImpulse> trial_impulse; // Distributed on the accepted particle trajectory.
};

namespace hydro_contact_detail {
using Clock=std::chrono::steady_clock;
inline double elapsed(Clock::time_point start){return std::chrono::duration<double>(Clock::now()-start).count();}

inline bool finite(const HydrodynamicImpulse& j){return std::isfinite(j.linear.x)&&std::isfinite(j.linear.y)&&std::isfinite(j.angular);}

// An impulse/angular impulse with respect to ONE fixed global origin. Convert
// its angular part to the body's current center at each application. Accounting
// for this orbital moment is necessary when the center moves during subcycling.
inline void kick(std::vector<Body>& bodies,const std::vector<HydrodynamicImpulse>& load,double fraction){
    for(std::size_t i=0;i<bodies.size();++i){
        auto& b=bodies[i];if(b.fixed)continue;
        const Vec2 dp=load[i].linear*fraction;
        b.v+=dp/b.mass;
        b.omega+=(fraction*load[i].angular-cross(b.x,dp))/b.inertia;
    }
}

inline void add_stats(WetParticleStats& total,const WetParticleStats& part){
    total.peak_contacts=std::max(total.peak_contacts,part.peak_contacts);
    total.max_overlap=std::max(total.max_overlap,part.max_overlap);
    total.min_core_gap=std::min(total.min_core_gap,part.min_core_gap);
    total.near_physical_dissipation+=part.near_physical_dissipation;
    total.near_numerical_dissipation+=part.near_numerical_dissipation;
    total.near_max_energy_residual=std::max(total.near_max_energy_residual,part.near_max_energy_residual);
    total.near_max_solve_residual=std::max(total.near_max_solve_residual,part.near_max_solve_residual);
    for(std::size_t i=0;i<total.near_impulse.size();++i){
        total.near_impulse[i]+=part.near_impulse[i];
        total.near_angular_global[i]+=part.near_angular_global[i];
    }
}

inline double velocity_norm(const Body& body,const HydrodynamicImpulse& j){
    if(!finite(j))throw std::runtime_error("Nonfinite hydrodynamic exchange impulse");
    const double value=std::max(norm(j.linear)/body.mass,
        body.radius*std::abs(j.angular-cross(body.x,j.linear))/body.inertia);
    if(!std::isfinite(value))throw std::runtime_error("Nonfinite generalized exchange velocity");
    return value;
}
}

// One dt=1 lattice step. The fluid collision/stream predictor is frozen ONCE.
// A trial integrated physical hydrodynamic impulse (J,L_global) is distributed
// uniformly in time, using half kicks around each physical-stiffness substep.
// This affects positions, rotations, contact history, and optional near-field
// resistance during the trial. Only endpoint IBM geometry is used by the fluid;
// this is not a monolithic time-continuous solve or a claim of second order.
//
// At endpoint x_e, subtract (J/M,(L_global-x_e cross J)/I) from the candidate
// rigid velocities before calling the ordinary dynamic IBM projection. Thus
// the projection contributes its *physical* impulse, including fictitious
// interior correction, ONCE. The accepted rigid velocity and fluid satisfy the
// current no-slip solve; differences from the particle-trajectory endpoint are
// bounded by the reported outer residual. All rejected histories are discarded.
inline HydroContactStepStats advance_hydro_contact_iterated(LBM& fluid,IBM& ib,DEM& dem,
        NearField& near,std::vector<Body>& bodies,int substeps,const HydroContactControls& controls={}){
    using namespace hydro_contact_detail;
    if(substeps<1||controls.max_iterations<1||!std::isfinite(controls.relative_tolerance)||
       !std::isfinite(controls.absolute_tolerance)||!std::isfinite(controls.relaxation)||
       controls.relative_tolerance<0||controls.absolute_tolerance<0||
       !(controls.relative_tolerance>0||controls.absolute_tolerance>0)||
       !(controls.relaxation>0&&controls.relaxation<=1))
        throw std::invalid_argument("Invalid iterated hydro-contact exchange controls");
    if(bodies.empty()||ib.old_interior.size()!=bodies.size())
        throw std::invalid_argument("Hydro-contact exchange needs initialized IBM and nonempty matching body state");
    std::vector<HydrodynamicImpulse> guess(bodies.size());
    if(!ib.hydrodynamic_impulse.empty()){
        if(ib.hydrodynamic_impulse.size()!=bodies.size())throw std::invalid_argument("Hydrodynamic warm-start size mismatch");
        guess=ib.hydrodynamic_impulse;
    }
    for(std::size_t i=0;i<bodies.size();++i){const auto& b=bodies[i];
        if(!(b.mass>0&&b.inertia>0&&b.radius>0)||!std::isfinite(b.mass)||!std::isfinite(b.inertia)||!std::isfinite(b.radius))
            throw std::invalid_argument("Hydro-contact exchange requires positive finite physical mass, inertia and radius");
        if(b.fixed)guess[i]={};
        if(!finite(guess[i]))throw std::invalid_argument("Nonfinite hydrodynamic warm start");
    }

    HydroContactStepStats result;
    // Transactional construction: the caller's fluid, bodies, stateful DEM,
    // near-field and IBM caches/interior snapshot are never used as trial work.
    LBM trial_fluid=fluid;
    auto start=Clock::now();trial_fluid.collide_stream();result.fluid_seconds=elapsed(start);
    result.periodic_angular_flux=trial_fluid.periodic_angular_flux();
    const auto predictor_f=trial_fluid.f;
    const auto predictor_u=trial_fluid.u;
    const auto predictor_rho=trial_fluid.rho;
    const double h=1.0/substeps;
    for(int iteration=1;iteration<=controls.max_iterations;++iteration){
        if(iteration>1&&!ib.compact_commit){trial_fluid.f=predictor_f;trial_fluid.u=predictor_u;trial_fluid.rho=predictor_rho;}
        auto trial_bodies=bodies;DEM trial_dem=dem;NearField trial_near=near;IBM trial_ib=ib;
        WetParticleStats particles;
        particles.near_impulse.resize(bodies.size());particles.near_angular_global.resize(bodies.size());
        start=Clock::now();
        for(int k=0;k<substeps;++k){
            kick(trial_bodies,guess,0.5*h);
            const auto part=advance_wet_particles(trial_dem,trial_near,trial_bodies,h,1);
            add_stats(particles,part);
            kick(trial_bodies,guess,0.5*h);
        }
        result.particle_seconds+=elapsed(start);

        // Remove the trial global impulse at this common endpoint, not the
        // separately accumulated spin increments about earlier body centers.
        kick(trial_bodies,guess,-1.0);
        start=Clock::now();trial_ib.couple(trial_fluid,trial_bodies);result.coupling_seconds+=elapsed(start);
        result.outer_iterations=iteration;result.ibm_iterations+=trial_ib.stats.iterations;
        result.ibm_rebuilds+=trial_ib.stats.preconditioner_rebuilt;
        double residual=0.0,scale=0.0;
        for(std::size_t i=0;i<bodies.size();++i){const auto& b=trial_bodies[i];if(b.fixed)continue;
            const auto& value=trial_ib.hydrodynamic_impulse[i];
            const HydrodynamicImpulse diff{value.linear-guess[i].linear,value.angular-guess[i].angular};
            residual=std::max(residual,velocity_norm(b,diff));
            scale=std::max({scale,velocity_norm(b,guess[i]),velocity_norm(b,value)});
        }
        result.residual_velocity=residual;result.tolerance_velocity=controls.absolute_tolerance+controls.relative_tolerance*scale;
        if(!std::isfinite(result.tolerance_velocity))throw std::runtime_error("Nonfinite hydro-contact exchange threshold");
        if(residual<=result.tolerance_velocity){
            result.particles=std::move(particles);result.trial_impulse=std::move(guess);
            // The final half kick and exact IBM endpoint projection may alter
            // velocity-dependent contact force diagnostics. Query dt=0 only;
            // no second contact-history increment is taken.
            trial_dem.evaluate(trial_bodies,0.0);
            fluid.f.swap(trial_fluid.f);fluid.u.swap(trial_fluid.u);fluid.rho.swap(trial_fluid.rho);
            // LBM's private second population buffer is scratch: every entry
            // is overwritten on the next collide_stream().
            bodies.swap(trial_bodies);dem=std::move(trial_dem);near=std::move(trial_near);ib=std::move(trial_ib);
            return result;
        }
        for(std::size_t i=0;i<bodies.size();++i)if(!bodies[i].fixed){const auto& value=trial_ib.hydrodynamic_impulse[i];
            guess[i].linear+=(value.linear-guess[i].linear)*controls.relaxation;
            guess[i].angular+=(value.angular-guess[i].angular)*controls.relaxation;
        }
        if(ib.compact_commit&&iteration<controls.max_iterations){
            // Indexed IBM commit can change only these post-stream f/u values;
            // rho is unchanged. Undo EVERY node in the rejected trial's full
            // support, not its intersection with a predicted future support.
            // The next trial independently constructs all current markers/nodes.
            for(int q=0;q<LBM::q_count;++q){const std::size_t offset=std::size_t(q)*trial_fluid.n;
                for(int cell:trial_ib.active_nodes)trial_fluid.f[offset+cell]=predictor_f[offset+cell];
            }
            for(int cell:trial_ib.active_nodes)trial_fluid.u[cell]=predictor_u[cell];
        }
    }
    std::ostringstream message;message<<"Hydro-contact exchange failed after "<<result.outer_iterations
        <<" trials: velocity residual "<<result.residual_velocity<<" > "<<result.tolerance_velocity
        <<"; step-start state retained";
    throw std::runtime_error(message.str());
}
}
