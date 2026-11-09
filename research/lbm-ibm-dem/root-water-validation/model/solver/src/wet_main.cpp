#include "ibm.hpp"
#include "wet_stepper.hpp"
#include "hydro_contact_step.hpp"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

using namespace ibdem;
namespace {
using Clock=std::chrono::steady_clock;
struct Momentum { Vec2 p; double l=0; };
Momentum lattice_momentum(const LBM& f) {
    Momentum q;
    for(int i=0;i<f.n;++i) {
        const Vec2 p=f.u[i]*f.rho[i]; q.p+=p;
        q.l+=cross({double(i%f.nx),double(i/f.nx)},p);
    }
    return q;
}
Momentum physical_momentum(const LBM& f,const IBM& ib,const std::vector<Body>& b) {
    auto q=lattice_momentum(f);
    for(std::size_t i=0;i<b.size();++i) {
        q.p-=ib.old_interior[i].p; q.l-=ib.old_interior[i].angular;
        q.p+=b[i].v*b[i].mass;
        q.l+=cross(b[i].x,b[i].v*b[i].mass)+b[i].inertia*b[i].omega;
    }
    return q;
}
double fluid_mass(const LBM& f) { double m=0;for(double x:f.rho)m+=x;return m; }
double seconds(Clock::time_point t) {return std::chrono::duration<double>(Clock::now()-t).count();}
}
int main(int argc,char** argv) {
 try {
    std::string name="normal",mode="fast",lubrication="off",exchange="split",commit="dense",csv,state;
    HydroContactControls exchange_controls;
    int resolution=8,substeps=8,block_size=2;
    double dt_factor=1,t_end=2,offset_ratio=0.125,cutoff=2,minimum_gap_ratio=0.02,warmup=0,retraction=0;
    double density=1.2,viscosity=0.1,normal_speed=0.16,tangent_speed=0.08;
    double kn=128,kt=51.2,cn=1,ct=0.1,friction=0.4;
    for(int i=1;i<argc;++i) {
        std::string a=argv[i];
        if(a=="--help") {
            std::cout<<"wet_impact --case normal|oblique --mode ref|fast --resolution cells_per_radius --dt-factor value --time physical_time --warmup prescribed_geometry_time --retraction lattice_distance --substeps N --offset ratio --lubrication off|on --cutoff lattice_gap --min-gap physical_gap --csv FILE --state FILE\n"
                <<"Optional: --commit dense|active --exchange split|iterated --exchange-tol relative --exchange-atol lattice_velocity --exchange-relax (0,1] --exchange-max-iters N\n"
                <<"Defaults: dense commit, split exchange; iterative controls rtol=1e-7, atol=1e-12, relaxation=1, max=30.\n"
                <<"Physical reference units: smooth radius=1, rho_f=1; defaults nu=0.1, rho_p=1.2, kn=128, kt=51.2, cn=1, ct=.1, mu=.4. Explicit contact offset=.125 radius; illustrative, not microplastic calibration.\n";
            return 0;
        }
        if(i+1>=argc)throw std::invalid_argument("Option requires a value: "+a);
        std::string v=argv[++i];
        if(a=="--case")name=v;else if(a=="--mode")mode=v;else if(a=="--resolution")resolution=std::stoi(v);
        else if(a=="--substeps")substeps=std::stoi(v);else if(a=="--block-size")block_size=std::stoi(v);
        else if(a=="--dt-factor")dt_factor=std::stod(v);else if(a=="--time")t_end=std::stod(v);else if(a=="--warmup")warmup=std::stod(v);
        else if(a=="--offset")offset_ratio=std::stod(v);else if(a=="--lubrication")lubrication=v;else if(a=="--retraction")retraction=std::stod(v);
        else if(a=="--exchange")exchange=v;else if(a=="--commit")commit=v;
        else if(a=="--exchange-tol")exchange_controls.relative_tolerance=std::stod(v);
        else if(a=="--exchange-atol")exchange_controls.absolute_tolerance=std::stod(v);
        else if(a=="--exchange-relax")exchange_controls.relaxation=std::stod(v);
        else if(a=="--exchange-max-iters")exchange_controls.max_iterations=std::stoi(v);
        else if(a=="--cutoff")cutoff=std::stod(v);else if(a=="--min-gap")minimum_gap_ratio=std::stod(v);
        else if(a=="--density")density=std::stod(v);else if(a=="--nu")viscosity=std::stod(v);
        else if(a=="--normal-speed")normal_speed=std::stod(v);else if(a=="--tangent-speed")tangent_speed=std::stod(v);
        else if(a=="--kn")kn=std::stod(v);else if(a=="--kt")kt=std::stod(v);else if(a=="--cn")cn=std::stod(v);
        else if(a=="--ct")ct=std::stod(v);else if(a=="--friction")friction=std::stod(v);
        else if(a=="--csv")csv=v;else if(a=="--state")state=v;else throw std::invalid_argument("Unknown option: "+a);
    }
    if(name!="normal"&&name!="oblique")throw std::invalid_argument("Case must be normal or oblique");
    if(mode!="ref"&&mode!="fast")throw std::invalid_argument("Mode must be ref or fast");
    if(lubrication!="off"&&lubrication!="on")throw std::invalid_argument("Lubrication must be off or on");
    if(exchange!="split"&&exchange!="iterated")throw std::invalid_argument("Exchange must be split or iterated");
    if(commit!="dense"&&commit!="active")throw std::invalid_argument("Commit must be dense or active");
    if(!std::isfinite(exchange_controls.relative_tolerance)||!std::isfinite(exchange_controls.absolute_tolerance)||
       !std::isfinite(exchange_controls.relaxation)||exchange_controls.relative_tolerance<0||exchange_controls.absolute_tolerance<0||
       !(exchange_controls.relative_tolerance>0||exchange_controls.absolute_tolerance>0)||
       !(exchange_controls.relaxation>0&&exchange_controls.relaxation<=1)||exchange_controls.max_iterations<1)
        throw std::invalid_argument("Invalid exchange tolerances, relaxation or outer iteration limit");
    if(resolution<4||resolution>256||substeps<1||block_size<1||block_size>2)
        throw std::invalid_argument("Invalid resolution, substeps or block size");
    for(double x:{dt_factor,t_end,density,viscosity,normal_speed,offset_ratio,minimum_gap_ratio})
        if(!(x>0)||!std::isfinite(x))throw std::invalid_argument("Positive finite physical/time parameters required");
    for(double x:{kn,kt,cn,ct,friction,tangent_speed,cutoff,warmup,retraction})
        if(!(x>=0)||!std::isfinite(x))throw std::invalid_argument("Finite nonnegative contact parameters required");
    const auto total_start=Clock::now();
    const double R=resolution,dx=1/R,dt=dt_factor/(R*R);
    const double velocity_unit=dx/dt,force_unit=dx*dx*dx/(dt*dt),energy_unit=dx*dx*velocity_unit*velocity_unit;
    const int steps=static_cast<int>(std::ceil(t_end/dt-1e-12));
    LBM fluid(12*resolution,8*resolution,0.5+3*viscosity*dt_factor);
    const Vec2 center{0.5*(fluid.nx-1),0.5*(fluid.ny-1)};
    const double separation=(2+2*offset_ratio+0.01)*R;
    std::vector<Body> bodies{disk(0,center-Vec2{separation/2,0},R,density,false,offset_ratio*R),
                             disk(1,center+Vec2{separation/2,0},R,density,false,offset_ratio*R)};
    const double vn=normal_speed/velocity_unit,vt=name=="oblique"?tangent_speed/velocity_unit:0;
    bodies[0].v={0.5*vn,0.5*vt};bodies[1].v=-bodies[0].v;
    DEM dem;dem.kn=kn*dt*dt/(dx*dx);dem.kt=kt*dt*dt/(dx*dx);
    dem.cn=cn*dt/(dx*dx);dem.ct=ct*dt/(dx*dx);dem.mu=friction;
    NearField near;near.enabled=lubrication=="on";near.viscosity=viscosity*dt_factor;
    near.normal_cutoff=cutoff;near.tangential_cutoff=cutoff;near.min_gap=minimum_gap_ratio*R;
    IBM ib(mode=="ref"?IBM::Mode::Reference:IBM::Mode::CachedBlocks);
    ib.marker_retraction=retraction;
    ib.compact_commit=commit=="active";
    ib.max_bodies_per_block=block_size;ib.max_iterations=2400;ib.restart=120;
    ib.relative_tolerance=1e-10;ib.absolute_tolerance=1e-13;ib.initialize(fluid,bodies);
    // Optional prescribed-motion preparation constructs a velocity field at
    // frozen geometry. It defines an initial state, not a physical trajectory
    // before release, and is not assumed steady without its own convergence.
    const int preparation_steps=static_cast<int>(std::ceil(warmup/dt-1e-12));
    for(int step=0;step<preparation_steps;++step){fluid.collide_stream();ib.couple_prescribed(fluid,bodies);}
    if(preparation_steps)ib.initialize(fluid,bodies);
    ib.hydrodynamic_impulse.clear();
    const auto initial_momentum=physical_momentum(fluid,ib,bodies);
    const double initial_mass=fluid_mass(fluid);
    double boundary_angular=0,max_linear_drift=0,max_angular_drift=0,max_slip=0,max_speed=0;
    double min_gap=1e100,max_overlap=0,near_physical=0,near_numerical=0,near_energy_residual=0;
    double fluid_seconds=0,particle_seconds=0,coupling_seconds=0;
    double first_contact=-1,last_contact=-1,max_contact_force=0;
    std::size_t max_contacts=0;int iterations=0,rebuilds=0;
    long long outer_iterations=0, accepted_ibm_iterations=0, accepted_ibm_rebuilds=0;
    int outer_max_used=0;
    double exchange_seconds=0,exchange_max_residual=0,exchange_max_threshold=0,exchange_max_ratio=0;
    std::ofstream output;if(!csv.empty()){output.open(csv);if(!output)throw std::runtime_error("Cannot open trajectory CSV");
        output<<"time,time_nu_over_R2,gap_over_R,overlap_over_R,relative_normal_velocity,relative_tangential_velocity,omega_a,omega_b,normal_contact_force,tangential_contact_force,hydro_force_a_x,hydro_force_a_y,near_force_a_x,near_force_a_y,physical_momentum_error,angular_budget_error,near_physical_dissipation,near_numerical_dissipation,contacts\n";}
    auto record=[&](int step,const WetParticleStats& ws) {
        const Vec2 n=(bodies[1].x-bodies[0].x)/norm(bodies[1].x-bodies[0].x),t=perp(n);
        const double gap=(norm(bodies[1].x-bodies[0].x)-2*R)*dx;
        const double overlap=std::max(0.0,2*offset_ratio-gap);
        const auto q=physical_momentum(fluid,ib,bodies);
        const double dp=norm(q.p-initial_momentum.p)*dx*dx*velocity_unit;
        const double dl=std::abs(q.l-initial_momentum.l-boundary_angular)*dx*dx*dx*velocity_unit;
        max_linear_drift=std::max(max_linear_drift,dp);max_angular_drift=std::max(max_angular_drift,dl);
        const double fn=-dot(bodies[0].force,n)*force_unit,ft=dot(bodies[0].force,t)*force_unit;
        max_contact_force=std::max(max_contact_force,fn);
        if(output) {
            const Vec2 hf=ib.hydrodynamic_impulse.empty()?Vec2{}:ib.hydrodynamic_impulse[0].linear*force_unit;
            const Vec2 nf=ws.near_impulse.empty()?Vec2{}:ws.near_impulse[0]*force_unit;
            output<<std::setprecision(17)<<step*dt<<','<<step*dt*viscosity<<','<<gap<<','<<overlap<<','
                <<dot(bodies[0].v-bodies[1].v,n)*velocity_unit<<','<<dot(bodies[0].v-bodies[1].v,t)*velocity_unit<<','
                <<bodies[0].omega/dt<<','<<bodies[1].omega/dt<<','<<fn<<','<<ft<<','<<hf.x<<','<<hf.y<<','<<nf.x<<','<<nf.y<<','
                <<dp<<','<<dl<<','<<near_physical<<','<<near_numerical<<','<<dem.stats.contact_count<<'\n';
        }
    };
    dem.evaluate(bodies);record(0,{});
    for(int step=1;step<=steps;++step) {
        WetParticleStats ws;
        if(exchange=="split"){
            auto start=Clock::now();ws=advance_wet_particles(dem,near,bodies,1,substeps);particle_seconds+=seconds(start);
            start=Clock::now();fluid.collide_stream();fluid_seconds+=seconds(start);
            boundary_angular+=fluid.periodic_angular_flux();
            start=Clock::now();ib.couple(fluid,bodies);coupling_seconds+=seconds(start);
            iterations+=ib.stats.iterations;rebuilds+=ib.stats.preconditioner_rebuilt;
        }else{
            auto start=Clock::now();auto trial=advance_hydro_contact_iterated(fluid,ib,dem,near,bodies,substeps,exchange_controls);
            exchange_seconds+=seconds(start);ws=std::move(trial.particles);
            fluid_seconds+=trial.fluid_seconds;particle_seconds+=trial.particle_seconds;coupling_seconds+=trial.coupling_seconds;
            boundary_angular+=trial.periodic_angular_flux;
            iterations+=trial.ibm_iterations;rebuilds+=trial.ibm_rebuilds;
            outer_iterations+=trial.outer_iterations;outer_max_used=std::max(outer_max_used,trial.outer_iterations);
            exchange_max_residual=std::max(exchange_max_residual,trial.residual_velocity);
            exchange_max_threshold=std::max(exchange_max_threshold,trial.tolerance_velocity);
            const double ratio=trial.tolerance_velocity>0?trial.residual_velocity/trial.tolerance_velocity:0.0;
            exchange_max_ratio=std::max(exchange_max_ratio,ratio);
        }
        min_gap=std::min(min_gap,ws.min_core_gap*dx);max_overlap=std::max(max_overlap,ws.max_overlap*dx);
        max_contacts=std::max(max_contacts,ws.peak_contacts);
        if(ws.peak_contacts){if(first_contact<0)first_contact=(step-1)*dt;last_contact=step*dt;}
        near_physical+=ws.near_physical_dissipation*energy_unit;near_numerical+=ws.near_numerical_dissipation*energy_unit;
        near_energy_residual=std::max(near_energy_residual,ws.near_max_energy_residual*energy_unit);
        accepted_ibm_iterations+=ib.stats.iterations;accepted_ibm_rebuilds+=ib.stats.preconditioner_rebuilt;
        max_slip=std::max(max_slip,ib.stats.max_slip*velocity_unit);
        for(auto u:fluid.u)max_speed=std::max(max_speed,norm(u));
        if(!std::isfinite(max_speed)||max_speed>0.1)throw std::runtime_error("Wet case exceeded declared lattice speed limit0.1; refine timestep/grid before interpretation");
        if(exchange=="split")dem.evaluate(bodies,0.0);
        record(step,ws);
    }
    const double elapsed=seconds(total_start);
    if(!state.empty()) {
        std::ofstream f(state,std::ios::binary);if(!f)throw std::runtime_error("Cannot open checkpoint");
        f.write(reinterpret_cast<const char*>(fluid.f.data()),fluid.f.size()*sizeof(double));
        for(const auto& b:bodies){double a[]={b.x.x,b.x.y,b.v.x,b.v.y,b.angle,b.omega};f.write(reinterpret_cast<const char*>(a),sizeof(a));}
    }
    const Vec2 n=(bodies[1].x-bodies[0].x)/norm(bodies[1].x-bodies[0].x),t=perp(n);
    const auto rho_bounds=std::minmax_element(fluid.rho.begin(),fluid.rho.end());
    std::cout<<std::setprecision(17)<<"{\"case\":\""<<name<<"\",\"mode\":\""<<mode<<"\",\"lubrication\":\""<<lubrication<<"\",\"resolution\":"<<resolution
        <<",\"exchange\":\""<<exchange<<"\",\"commit\":\""<<commit<<"\",\"exchange_tol\":"<<exchange_controls.relative_tolerance
        <<",\"exchange_atol_lattice\":"<<exchange_controls.absolute_tolerance<<",\"exchange_relax\":"<<exchange_controls.relaxation
        <<",\"exchange_max_iters_limit\":"<<exchange_controls.max_iterations<<",\"exchange_outer_iterations\":"<<outer_iterations
        <<",\"exchange_max_iterations_used\":"<<outer_max_used<<",\"exchange_max_residual_velocity_lattice\":"<<exchange_max_residual
        <<",\"exchange_max_tolerance_velocity_lattice\":"<<exchange_max_threshold<<",\"exchange_max_fraction_of_threshold\":"<<exchange_max_ratio
        <<",\"exchange_seconds\":"<<exchange_seconds<<",\"accepted_ibm_iterations\":"<<accepted_ibm_iterations<<",\"accepted_ibm_rebuilds\":"<<accepted_ibm_rebuilds
        <<",\"nx\":"<<fluid.nx<<",\"ny\":"<<fluid.ny<<",\"bodies\":"<<bodies.size()
        <<",\"dt_factor\":"<<dt_factor<<",\"dt\":"<<dt<<",\"steps\":"<<steps<<",\"time\":"<<steps*dt<<",\"preparation_time\":"<<preparation_steps*dt<<",\"preparation_steps\":"<<preparation_steps<<",\"substeps\":"<<substeps<<",\"block_size\":"<<block_size
        <<",\"offset_ratio\":"<<offset_ratio<<",\"marker_retraction\":"<<retraction<<",\"density_ratio\":"<<density<<",\"nu\":"<<viscosity<<",\"kn\":"<<kn<<",\"kt\":"<<kt<<",\"cn\":"<<cn<<",\"ct\":"<<ct<<",\"friction\":"<<friction
        <<",\"cutoff_lattice\":"<<cutoff<<",\"min_gap_regularization\":"<<minimum_gap_ratio<<",\"normal_speed_initial\":"<<normal_speed<<",\"tangent_speed_initial\":"<<(name=="oblique"?tangent_speed:0)
        <<",\"seconds\":"<<elapsed<<",\"fluid_seconds\":"<<fluid_seconds<<",\"particle_seconds\":"<<particle_seconds<<",\"coupling_seconds\":"<<coupling_seconds
        <<",\"iterations\":"<<iterations<<",\"rebuilds\":"<<rebuilds<<",\"max_contacts\":"<<max_contacts<<",\"first_contact_bracket_start\":"<<first_contact<<",\"last_contact_bracket_end\":"<<last_contact
        <<",\"minimum_core_gap\":"<<min_gap<<",\"max_contact_overlap\":"<<max_overlap<<",\"peak_endpoint_contact_force\":"<<max_contact_force
        <<",\"momentum_drift\":"<<max_linear_drift<<",\"angular_budget_drift\":"<<max_angular_drift<<",\"mass_relative_drift\":"<<std::abs(fluid_mass(fluid)-initial_mass)/initial_mass
        <<",\"max_marker_slip\":"<<max_slip<<",\"max_lattice_speed\":"<<max_speed<<",\"min_density_final\":"<<*rho_bounds.first<<",\"max_density_final\":"<<*rho_bounds.second
        <<",\"near_physical_dissipation\":"<<near_physical<<",\"near_numerical_dissipation\":"<<near_numerical<<",\"near_energy_residual\":"<<near_energy_residual
        <<",\"normal_velocity_final\":"<<dot(bodies[0].v-bodies[1].v,n)*velocity_unit<<",\"tangent_velocity_final\":"<<dot(bodies[0].v-bodies[1].v,t)*velocity_unit
        <<",\"omega_a_final\":"<<bodies[0].omega/dt<<",\"omega_b_final\":"<<bodies[1].omega/dt<<"}\n";
    return 0;
 }catch(const std::exception& e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}
}
