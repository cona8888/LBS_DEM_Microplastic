#include "dem.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>

namespace {
using namespace ibdem;

double kinetic(const std::vector<Body>& b) {
    double e=0.0;
    for (const auto& p:b) if (!p.fixed)
        e+=0.5*p.mass*dot(p.v,p.v)+0.5*p.inertia*p.omega*p.omega;
    return e;
}
Vec2 momentum(const std::vector<Body>& b) {
    Vec2 p;
    for (const auto& x:b) if (!x.fixed) p+=x.mass*x.v;
    return p;
}
double angularMomentum(const std::vector<Body>& b) {
    double l=0.0;
    for (const auto& p:b) if (!p.fixed)
        l+=cross(p.x,p.mass*p.v)+p.inertia*p.omega;
    return l;
}
Vec2 rotate(Vec2 x, double a) {
    return {std::cos(a)*x.x-std::sin(a)*x.y,
            std::sin(a)*x.x+std::cos(a)*x.y};
}
std::vector<Body> unitMassCollision() {
    std::vector<Body> b={disk(1,{-0.5,0},0.5,4.0/pi),
                         disk(2,{0.5,0},0.5,4.0/pi)};
    b[0].v={1,0}; b[1].v={-1,0};
    return b;
}
struct CollisionResult { double error=0.0, energy_error=0.0, restitution=0.0; };

CollisionResult conservative(int n) {
    auto b=unitMassCollision();
    DEM d; d.kn=100; d.kt=0; d.cn=0; d.ct=0; d.mu=0;
    const double w=std::sqrt(200.0), t=0.75*pi/w;
    const double initial=kinetic(b);
    double energy_error=0;
    for (int i=0;i<n;++i) {
        d.advance(b,t/n,1);
        energy_error=std::max(energy_error,std::abs(kinetic(b)+d.stats.elastic_energy-initial)/initial);
    }
    const double overlap=2.0*std::sin(w*t)/w;
    const double exact_x=-0.5+0.5*overlap, exact_v=std::cos(w*t);
    return {std::abs(b[0].x.x-exact_x)+std::abs(b[0].v.x-exact_v),energy_error,0};
}

CollisionResult damped(int n, double* exact=nullptr) {
    auto b=unitMassCollision();
    DEM d; d.kn=100; d.kt=0; d.cn=5; d.ct=0; d.mu=0;
    const double m_eff=0.5, eta=d.cn/(2*m_eff);
    const double wd=std::sqrt(d.kn/m_eff-eta*eta);
    // Repulsive/clipped dashpot ends force contact at Fn=0, not delta=0.
    // Schwager & Poschel (2007), DOI 10.1007/s10035-007-0065-z.
    const double t_force=2*std::atan(wd/eta)/wd;
    const double e=std::exp(-eta*t_force);
    const double t_separate=t_force+d.cn/d.kn;
    d.advance(b,1.4*t_separate,n);
    const double measured=(b[1].v.x-b[0].v.x)/2;
    if (exact) *exact=e;
    return {std::abs(measured-e),0,measured};
}

} // namespace

// Standalone entry called by the root test runner. Every result is one line.
int run_dem_tests() {
    using namespace ibdem;
    std::cout<<std::setprecision(17);
    int failures=0;
    const auto report=[&](const std::string& name,bool passed,const std::string& values) {
        std::cout<<"TEST "<<name<<" "<<(passed?"PASS":"FAIL")<<" "<<values<<"\n";
        if (!passed) ++failures;
    };
    const auto number=[](double x) { std::ostringstream s; s<<std::setprecision(17)<<x; return s.str(); };

    try {
        std::vector<Body> b={disk(10,{-0.93,0.1},1,1),disk(2,{0.98,0.3},1,1)};
        b[0].v={0.3,-0.6}; b[1].v={-0.4,0.2};
        b[0].omega=0.7; b[1].omega=-0.2;
        DEM d; d.kn=100; d.kt=40; d.cn=2; d.ct=0.7; d.mu=0.35;
        d.evaluate(b,0.01);
        const double force_error=norm(b[0].force+b[1].force);
        const double torque_error=std::abs(cross(b[0].x,b[0].force)+cross(b[1].x,b[1].force)+b[0].torque+b[1].torque);
        const double scale=1+norm(b[0].force);
        report("dem_action_reaction",force_error<1e-13*scale && torque_error<1e-13*scale && d.stats.force_count==1,
               "force_error="+number(force_error)+" total_torque_error="+number(torque_error)+" max_overlap="+number(d.stats.max_overlap));
    } catch (const std::exception& e) { report("dem_action_reaction",false,std::string("exception=")+e.what()); }

    try {
        const auto a=conservative(24), b=conservative(48), c=conservative(96);
        const double order=std::log(b.error/c.error)/std::log(2.0);
        auto full=unitMassCollision();
        DEM d; d.kn=100; d.kt=0; d.cn=0; d.ct=0; d.mu=0;
        d.advance(full,1.5*pi/std::sqrt(200.0),300);
        const double restitution=(full[1].v.x-full[0].v.x)/2;
        report("dem_conservative_collision",a.error>b.error && b.error>c.error && order>1.8 && c.energy_error<1e-3 && std::abs(restitution-1)<1e-4,
               "error24="+number(a.error)+" error48="+number(b.error)+" error96="+number(c.error)+" observed_order="+number(order)+" energy_error96="+number(c.energy_error)+" restitution="+number(restitution));
    } catch (const std::exception& e) { report("dem_conservative_collision",false,std::string("exception=")+e.what()); }

    try {
        double exact=0;
        const auto a=damped(100,&exact), b=damped(200), c=damped(400);
        report("dem_clipped_damped_restitution",a.error>b.error && b.error>c.error && c.error<5e-5,
               "analytic="+number(exact)+" measured400="+number(c.restitution)+" error100="+number(a.error)+" error200="+number(b.error)+" error400="+number(c.error));
    } catch (const std::exception& e) { report("dem_clipped_damped_restitution",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{-0.95,0},1,1),disk(2,{0.95,0},1,1)};
        b[0].v={0,1}; b[1].v={0,-1};
        DEM d; d.kn=100; d.kt=40; d.cn=0; d.ct=0; d.mu=0.2;
        d.evaluate(b,0.1);
        const double xi=d.tangentialHistory(1,2);
        const Vec2 f=b[0].force;
        const double ratio=d.stats.max_friction_ratio;
        for (int i=0;i<5;++i) d.evaluate(b,0);
        const double query_error=std::abs(xi-d.tangentialHistory(1,2));
        const double angle=0.67, omega=0.9;
        for (auto& p:b) { p.x=rotate(p.x,angle); p.v=omega*perp(p.x); p.omega=omega; }
        d.evaluate(b,0.02); // Rigid rotation of the pair has zero contact slip.
        const double objectivity_error=norm(b[0].force-rotate(f,angle));
        const double history_rotation_error=std::abs(xi-d.tangentialHistory(1,2));
        const Vec2 joined=b[1].x;
        b[1].x=b[0].x+rotate({3,0},angle);
        d.evaluate(b,0);
        const bool cleared=d.historySize()==0;
        b[1].x=joined;
        for (auto& p:b) { p.v={}; p.omega=0; }
        d.evaluate(b,0);
        const Vec2 tangent=perp((b[1].x-b[0].x)/norm(b[1].x-b[0].x));
        const double reset_force=std::abs(dot(b[0].force,tangent));
        report("dem_friction_history",ratio<=d.mu+1e-13 && std::abs(ratio-d.mu)<1e-12 && query_error==0 && objectivity_error<1e-11 && history_rotation_error<1e-12 && cleared && reset_force<1e-12,
               "friction_ratio="+number(ratio)+" mu="+number(d.mu)+" query_history_error="+number(query_error)+" rotation_force_error="+number(objectivity_error)+" rotation_history_error="+number(history_rotation_error)+" reset_tangent_force="+number(reset_force));
    } catch (const std::exception& e) { report("dem_friction_history",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{-0.95,0},1,1),disk(2,{0.95,0},1,1)};
        b[0].v={0,1}; b[1].v={0,-1};
        DEM d; d.kn=100; d.kt=40; d.cn=0; d.ct=100; d.mu=0.2;
        const double h=0.1, vt=2;
        d.evaluate(b,h);
        const double xi=d.tangentialHistory(1,2);
        const double cap=d.mu*100*0.1;
        const double exact_xi=h*cap/(d.ct+h*d.kt);
        const double stored=0.5*d.kt*xi*xi;
        const double contact_work=std::abs(b[0].force.y)*vt*h;
        const double dashpot_dissipation=d.ct*xi*xi/h;
        const double plastic_dissipation=cap*(h*vt-xi);
        const double balance=stored+dashpot_dissipation+plastic_dissipation-contact_work;
        report("dem_tangential_viscous_return_map",xi>=0 && xi<=cap/d.kt && std::abs(xi-exact_xi)<1e-13 && stored<=contact_work && balance<=1e-13,
               "history="+number(xi)+" elastic_energy="+number(stored)+" applied_work="+number(contact_work)+" discrete_energy_residual="+number(balance));
    } catch (const std::exception& e) { report("dem_tangential_viscous_return_map",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{-0.95,0},1,1),disk(2,{0.95,0},1,1)};
        b[0].v={0.1,0.4}; b[1].v={-0.2,-0.1};
        b[0].omega=0.2; b[1].omega=-0.3;
        const Vec2 initial_p=momentum(b);
        const double initial_l=angularMomentum(b);
        DEM d; d.kn=100; d.kt=30; d.cn=1; d.ct=0; d.mu=0.4;
        d.advance(b,0.1,200);
        const double pe=norm(momentum(b)-initial_p), le=std::abs(angularMomentum(b)-initial_l);
        report("dem_integrated_momentum",pe<1e-11 && le<1e-11,
               "linear_error="+number(pe)+" angular_error="+number(le));
    } catch (const std::exception& e) { report("dem_integrated_momentum",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{0,0},0.5,4.0/pi),disk(2,{5,0},0.5,4.0/pi,true)};
        b[0].v={0.2,-0.1}; b[0].omega=0.3;
        const double t=0.2;
        const Vec2 force={0.4,0.6}; const double torque=0.15;
        const Vec2 exact_x=b[0].x+t*b[0].v+0.5*t*t*force/b[0].mass;
        const double exact_angle=b[0].angle+t*b[0].omega+0.5*t*t*torque/b[0].inertia;
        DEM d;
        d.advance(b,t,7,{force,{3,4}},{torque,9});
        const double err=norm(b[0].x-exact_x)+std::abs(b[0].angle-exact_angle);
        report("dem_external_force_and_fixed_body",err<1e-13 && b[1].x.x==5 && b[1].x.y==0 && b[1].angle==0,
               "trajectory_error="+number(err)+" fixed_x="+number(b[1].x.x));
    } catch (const std::exception& e) { report("dem_external_force_and_fixed_body",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{0,0},1,2,false,0.08),
                            disk(2,{1.88,0},0.8,3,false,0.03)};
        const double mass_a=b[0].mass, mass_b=b[1].mass;
        const double inertia_a=b[0].inertia, inertia_b=b[1].inertia;
        b[0].v={0,0.3}; b[1].v={0,-0.2};
        b[0].omega=0.4; b[1].omega=-0.1;
        const double core_gap=norm(b[1].x-b[0].x)-b[0].radius-b[1].radius;
        const double overlap=b[0].contactRadius()+b[1].contactRadius()-norm(b[1].x-b[0].x);
        DEM d; d.kn=100; d.kt=40; d.cn=0; d.ct=0; d.mu=0.3;
        d.evaluate(b,0.01);
        const double torque_error=std::abs(cross(b[0].x,b[0].force)+cross(b[1].x,b[1].force)+b[0].torque+b[1].torque);
        const double normal_error=std::abs(-b[0].force.x-d.kn*overlap);
        const bool envelope_contact=d.stats.contact_count==1 && core_gap>0 && overlap>0;
        const bool physical_unchanged=b[0].radius==1 && b[1].radius==0.8 &&
            b[0].mass==mass_a && b[1].mass==mass_b &&
            b[0].inertia==inertia_a && b[1].inertia==inertia_b && d.kn==100;
        b[0].contact_offset=0; b[1].contact_offset=0;
        d.evaluate(b,0);
        const bool smooth_separated=d.stats.contact_count==0 && d.historySize()==0 &&
            norm(b[0].force)==0 && norm(b[1].force)==0;
        report("dem_contact_envelope",envelope_contact && physical_unchanged && smooth_separated && torque_error<1e-12 && normal_error<1e-12,
               "hydrodynamic_gap="+number(core_gap)+" contact_overlap="+number(overlap)+" normal_force_error="+number(normal_error)+" total_torque_error="+number(torque_error)+" physical_mass_inertia_unchanged="+std::to_string(physical_unchanged));
    } catch (const std::exception& e) { report("dem_contact_envelope",false,std::string("exception=")+e.what()); }

    try {
        DEM d;
        int rejected=0;
        for (double offset : {-0.01,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}) {
            std::vector<Body> b={disk(1,{0,0},1,1)};
            b[0].contact_offset=offset;
            try { d.evaluate(b,0); } catch (const std::invalid_argument&) { ++rejected; }
        }
        try { auto b=disk(1,{0,0},1,1,false,-0.01); (void)b; }
        catch (const std::invalid_argument&) { ++rejected; }
        const Body plain=disk(1,{0,0},1,1);
        report("dem_contact_offset_guards",rejected==4 && plain.contact_offset==0 && plain.contactRadius()==plain.radius,
               "rejected_cases="+std::to_string(rejected)+" default_offset="+number(plain.contact_offset));
    } catch (const std::exception& e) { report("dem_contact_offset_guards",false,std::string("exception=")+e.what()); }

    return failures;
}
