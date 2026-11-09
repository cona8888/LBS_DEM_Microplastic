#include "wet_stepper.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

namespace {
using namespace ibdem;

struct NormalResult {
    double error=0,overlap_error=0,velocity_error=0;
    double minimum_gap=0,near_energy_residual=0;
    bool parameters_unchanged=false,constant_resistance_regime=false;
};

NormalResult normalOracle(int substeps,double viscosity) {
    constexpr double radius=1,density=1.2,offset=0.1,vin=0.06;
    std::vector<Body> b={disk(1,{-1.1,0},radius,density,false,offset),
                         disk(2,{1.1,0},radius,density,false,offset)};
    b[0].v={0.5*vin,0}; b[1].v={-0.5*vin,0};
    const auto original=b;
    DEM dem;
    dem.kn=4; dem.kt=dem.cn=dem.ct=dem.mu=0;
    NearField near;
    near.viscosity=viscosity;
    near.min_gap=0.3;
    near.normal_cutoff=0.5;
    near.tangential_cutoff=0;

    // During this test the gap stays in (0,0.2], below the fixed positive
    // regularization floor 0.3. Rn is therefore CONSTANT. This is a specified
    // reduced particle/contact model, not a validation of continuum lubrication
    // at h/R=0.3 and not an LBM-IBM wet-collision validation.
    const double reduced_mass=b[0].mass*b[1].mass/(b[0].mass+b[1].mass);
    const double effective_radius=radius/2;
    const double resistance=3*pi*std::sqrt(2.0)*viscosity*std::pow(effective_radius,1.5)*
        (std::pow(near.min_gap,-1.5)-std::pow(near.normal_cutoff,-1.5));
    const double alpha=resistance/(2*reduced_mass);
    const double omega=std::sqrt(dem.kn/reduced_mass-alpha*alpha);
    const double time=0.75*pi/omega; // Strictly before first separation.
    const double exact_overlap=vin/omega*std::exp(-alpha*time)*std::sin(omega*time);
    const double exact_vn=vin*std::exp(-alpha*time)*
        (std::cos(omega*time)-alpha/omega*std::sin(omega*time));

    const auto ws=advance_wet_particles(dem,near,b,time,substeps);
    const double gap=norm(b[1].x-b[0].x)-2*radius;
    const double overlap=2*offset-gap;
    const double vn=b[0].v.x-b[1].v.x;
    const auto endpoint=near.pair_resistance(b[0],b[1]);
    NormalResult r;
    r.overlap_error=std::abs(overlap-exact_overlap);
    r.velocity_error=std::abs(vn-exact_vn);
    // Scale velocity error into displacement units to avoid mixing units.
    r.error=r.overlap_error+r.velocity_error/omega;
    r.minimum_gap=ws.min_core_gap;
    r.near_energy_residual=ws.near_max_energy_residual;
    r.parameters_unchanged=dem.kn==4 && dem.kt==0 && dem.cn==0 && dem.ct==0;
    for (std::size_t i=0;i<b.size();++i)
        r.parameters_unchanged=r.parameters_unchanged && b[i].radius==original[i].radius &&
            b[i].contact_offset==original[i].contact_offset && b[i].mass==original[i].mass &&
            b[i].inertia==original[i].inertia;
    r.constant_resistance_regime=ws.min_core_gap>0 && gap<near.min_gap && overlap>0 &&
        ws.max_overlap<2*offset && ws.peak_contacts==1 && endpoint.effective_gap==near.min_gap &&
        std::abs(endpoint.Rn-resistance)<1e-12*(1+resistance);
    return r;
}

Vec2 totalMomentum(const std::vector<Body>& b) {
    Vec2 p;
    for (const Body& body:b) p+=body.mass*body.v;
    return p;
}

double totalAngularMomentum(const std::vector<Body>& b) {
    double l=0;
    for (const Body& body:b) l+=cross(body.x,body.mass*body.v)+body.inertia*body.omega;
    return l;
}

Vec2 weightedPosition(const std::vector<Body>& b) {
    Vec2 x;
    for (const Body& body:b) x+=body.mass*body.x;
    return x;
}

} // namespace

int run_wet_stage_tests() {
    using namespace ibdem;
    std::cout<<std::setprecision(17);
    int failures=0;
    const auto report=[&](const std::string& name,bool pass,const std::string& values) {
        std::cout<<"TEST "<<name<<" "<<(pass?"PASS":"FAIL")<<" "<<values<<"\n";
        failures+=!pass;
    };
    const auto number=[](double x) { std::ostringstream s; s<<std::setprecision(17)<<x; return s.str(); };

    try {
        const auto a=normalOracle(32,0.005),b=normalOracle(64,0.005),c=normalOracle(128,0.005);
        const double order=std::log(b.error/c.error)/std::log(2.0);
        // At this weak viscosity, second-order conservative error still
        // dominates these three levels. Do not mislabel it as an asymptotic
        // second-order guarantee for the backward-Euler coupled stage.
        const bool refined=a.error>b.error && b.error>c.error && c.error<3e-6 && order>0.8;
        const bool valid=a.parameters_unchanged && b.parameters_unchanged && c.parameters_unchanged &&
            a.constant_resistance_regime && b.constant_resistance_regime && c.constant_resistance_regime;
        report("wet_stage_normal_contact_oracle",refined && valid && c.near_energy_residual<1e-12,
               "viscosity=0.005 error32="+number(a.error)+" error64="+number(b.error)+" error128="+number(c.error)+
               " observed_order="+number(order)+" overlap_error128="+number(c.overlap_error)+
               " velocity_error128="+number(c.velocity_error)+" minimum_core_gap="+number(c.minimum_gap)+
               " physical_parameters_unchanged="+std::to_string(valid));
    } catch (const std::exception& e) { report("wet_stage_normal_contact_oracle",false,std::string("exception=")+e.what()); }

    try {
        // A separately declared, stronger-drag material case exposes the
        // first-order BE term without changing mass, stiffness or the shell.
        const auto a=normalOracle(32,0.05),b=normalOracle(64,0.05),c=normalOracle(128,0.05);
        const double order=std::log(b.error/c.error)/std::log(2.0);
        const bool valid=a.parameters_unchanged && b.parameters_unchanged && c.parameters_unchanged &&
            a.constant_resistance_regime && b.constant_resistance_regime && c.constant_resistance_regime;
        report("wet_stage_first_order_drag",a.error>b.error && b.error>c.error && c.error<3e-5 &&
               order>0.85 && order<1.15 && valid && c.near_energy_residual<1e-12,
               "viscosity=0.05 error32="+number(a.error)+" error64="+number(b.error)+" error128="+number(c.error)+
               " observed_order="+number(order)+" minimum_core_gap="+number(c.minimum_gap));
    } catch (const std::exception& e) { report("wet_stage_first_order_drag",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{-1.1,0},1,1.2,false,0.15),
                             disk(2,{1.1,0},1,1.4,false,0.15),
                             disk(3,{0.2,1.65},0.6,1.1,false,0.15)};
        b[0].v={0.04,0.12}; b[0].omega=0.12;
        b[1].v={-0.03,-0.08}; b[1].omega=0.18;
        b[2].v={-0.02,0.01}; b[2].omega=-0.14;
        const auto original=b;
        const Vec2 p0=totalMomentum(b),x0=weightedPosition(b);
        const double l0=totalAngularMomentum(b),time=0.12;
        DEM dem; dem.kn=40; dem.kt=20; dem.cn=0.5; dem.ct=0.1; dem.mu=0.4;
        NearField near; near.viscosity=0.05; near.normal_cutoff=0.6;
        near.tangential_cutoff=0.6; near.min_gap=0.03;
        const auto ws=advance_wet_particles(dem,near,b,time,120);
        dem.evaluate(b,0); // Inspect accepted-state contact forces without slip accumulation.
        const double momentum_error=norm(totalMomentum(b)-p0);
        const double angular_error=std::abs(totalAngularMomentum(b)-l0);
        const double center_motion_error=norm(weightedPosition(b)-x0-time*p0);
        Vec2 near_sum;
        double near_angular=0,max_contact_torque=0;
        bool unchanged=dem.kn==40 && dem.kt==20 && dem.cn==0.5 && dem.ct==0.1;
        for (std::size_t i=0;i<b.size();++i) {
            near_sum+=ws.near_impulse[i];
            near_angular+=ws.near_angular_global[i];
            max_contact_torque=std::max(max_contact_torque,std::abs(b[i].torque));
            unchanged=unchanged && b[i].mass==original[i].mass && b[i].inertia==original[i].inertia &&
                b[i].radius==original[i].radius && b[i].contact_offset==original[i].contact_offset;
        }
        const bool interactions=ws.peak_contacts>=2 && max_contact_torque>1e-6 && dem.historySize()>0 &&
            ws.near_physical_dissipation>0 && ws.near_numerical_dissipation>0;
        report("wet_stage_friction_momentum",interactions && unchanged && momentum_error<1e-11 &&
               angular_error<1e-11 && center_motion_error<1e-11 && norm(near_sum)<1e-11 &&
               std::abs(near_angular)<1e-11 && ws.min_core_gap>0 &&
               dem.stats.max_friction_ratio<=dem.mu+1e-12 && ws.near_max_energy_residual<1e-12 &&
               ws.near_max_solve_residual<1e-11,
               "linear_error="+number(momentum_error)+" angular_error="+number(angular_error)+
               " mass_weighted_position_error="+number(center_motion_error)+" near_linear_ledger_error="+number(norm(near_sum))+
               " near_angular_ledger_error="+number(std::abs(near_angular))+" peak_contacts="+std::to_string(ws.peak_contacts)+
               " max_contact_torque="+number(max_contact_torque)+" minimum_core_gap="+number(ws.min_core_gap));
    } catch (const std::exception& e) { report("wet_stage_friction_momentum",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{-1.01,0},1,1.2,false,0.01),
                             disk(2,{1.01,0},1,1.2,false,0.01)};
        b[0].v={0.5,0}; b[1].v={-0.5,0};
        const double mass=b[0].mass,inertia=b[0].inertia;
        DEM dem; dem.kn=0.01; dem.kt=dem.cn=dem.ct=dem.mu=0;
        NearField near; near.enabled=false;
        bool rejected=false;
        try { advance_wet_particles(dem,near,b,0.1,1); }
        catch (const std::runtime_error& e) {
            rejected=std::string(e.what()).find("Smooth hydrodynamic cores")!=std::string::npos;
        }
        // Rejection is diagnostic; this helper is not a transactional rollback.
        // Crucially it does not repair the event by changing radii or stiffness.
        const bool unchanged=b[0].radius==1 && b[1].radius==1 && b[0].contact_offset==0.01 &&
            b[0].mass==mass && b[0].inertia==inertia && dem.kn==0.01;
        report("wet_stage_overcompression_guard",rejected && unchanged,
               "rejected="+std::to_string(rejected)+" physical_parameters_unchanged="+std::to_string(unchanged));
    } catch (const std::exception& e) { report("wet_stage_overcompression_guard",false,std::string("exception=")+e.what()); }

    return failures;
}
