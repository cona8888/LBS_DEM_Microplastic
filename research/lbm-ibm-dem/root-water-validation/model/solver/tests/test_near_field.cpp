#include "near_field.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>

namespace {
using namespace ibdem;

double dot6(const std::array<double,6>& a,const std::array<double,6>& b) {
    double result=0;
    for (int i=0;i<6;++i) result+=a[i]*b[i];
    return result;
}

// Independent coefficients written in the uncombined power-difference form.
std::array<double,2> referenceCoefficients(double ra,double rb,double gap,const NearField& nf) {
    const double effective=ra*rb/(ra+rb),h=std::max(gap,nf.min_gap);
    double normal=0,tangential=0;
    if (nf.normal_cutoff>0 && gap<nf.normal_cutoff)
        normal=3*pi*std::sqrt(2.0)*nf.viscosity*std::pow(effective,1.5)*
            (std::pow(h,-1.5)-std::pow(nf.normal_cutoff,-1.5));
    if (nf.tangential_cutoff>0 && gap<nf.tangential_cutoff)
        tangential=pi*nf.viscosity*std::sqrt(2*effective)*
            (1/std::sqrt(h)-1/std::sqrt(nf.tangential_cutoff));
    return {normal,tangential};
}

// Closed-form force/torque action independent of the implementation's mode
// outer-product assembly and mass-whitened Cholesky.
std::vector<double> referenceForce(const std::vector<Body>& bodies,const NearField& nf) {
    std::vector<double> f(3*bodies.size(),0);
    for (std::size_t a=0;a<bodies.size();++a) for (std::size_t b=a+1;b<bodies.size();++b) {
        if (bodies[a].fixed && bodies[b].fixed) continue;
        const Vec2 dx=bodies[b].x-bodies[a].x;
        const double distance=norm(dx),gap=distance-bodies[a].radius-bodies[b].radius;
        const Vec2 n=dx/distance,t=perp(n);
        const auto coeff=referenceCoefficients(bodies[a].radius,bodies[b].radius,gap,nf);
        const double la=0.5*(distance+bodies[a].radius-bodies[b].radius),lb=distance-la;
        const double beta=(la-lb)/distance;
        const Vec2 va=bodies[a].fixed?Vec2{}:bodies[a].v;
        const Vec2 vb=bodies[b].fixed?Vec2{}:bodies[b].v;
        const double wa=bodies[a].fixed?0:bodies[a].omega;
        const double wb=bodies[b].fixed?0:bodies[b].omega;
        const double vn=dot(va-vb,n),vt=dot(va-vb,t);
        const double slide=vt+la*wa+lb*wb;
        const double pump=beta*vt+la*wa-lb*wb;
        const Vec2 fa=-coeff[0]*vn*n-coeff[1]*(slide+beta*pump)*t;
        const double ta=-coeff[1]*la*(slide+pump);
        const double tb=-coeff[1]*lb*(slide-pump);
        f[3*a]+=fa.x; f[3*a+1]+=fa.y; f[3*a+2]+=ta;
        f[3*b]-=fa.x; f[3*b+1]-=fa.y; f[3*b+2]+=tb;
    }
    return f;
}

std::vector<double> denseSolve(std::vector<double> a,std::vector<double> b) {
    const std::size_t n=b.size();
    for (std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for (std::size_t i=k+1;i<n;++i)
            if (std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
        if (!(std::abs(a[pivot*n+k])>0)) throw std::runtime_error("Singular reference resistance system");
        for (std::size_t j=0;j<n;++j) std::swap(a[k*n+j],a[pivot*n+j]);
        std::swap(b[k],b[pivot]);
        for (std::size_t i=k+1;i<n;++i) {
            const double factor=a[i*n+k]/a[k*n+k];
            for (std::size_t j=k;j<n;++j) a[i*n+j]-=factor*a[k*n+j];
            b[i]-=factor*b[k];
        }
    }
    for (std::size_t i=n;i-- >0;) {
        for (std::size_t j=i+1;j<n;++j) b[i]-=a[i*n+j]*b[j];
        b[i]/=a[i*n+i];
    }
    return b;
}

std::vector<Body> mixedBodies() {
    std::vector<Body> b={disk(10,{0,0},1,1.2),
                         disk(20,{1.85,0},0.7,3,true),
                         disk(30,{0.4,1.5},0.4,2.1)};
    b[0].v={0.3,-0.2}; b[0].omega=0.45;
    b[2].v={-0.15,0.25}; b[2].omega=-0.3;
    return b;
}

NearField testLaw() {
    NearField n;
    n.viscosity=0.2; n.normal_cutoff=0.6; n.tangential_cutoff=0.5; n.min_gap=0.01;
    return n;
}

double frozenModalError(int steps) {
    NearField nf=testLaw();
    std::vector<Body> b={disk(1,{-1.05,0},1,1.2),disk(2,{1.05,0},1,1.2)};
    b[0].v={0.2,0.5}; b[1].v={-0.2,-0.5};
    b[0].omega=0.8; b[1].omega=-0.3;
    const double gap=0.1,lever=1.05;
    const auto coeff=referenceCoefficients(1,1,gap,nf);
    const double mass=b[0].mass,inertia=b[0].inertia;
    const double rate_n=coeff[0]*2/mass;
    const double rate_s=coeff[1]*(2/mass+2*lever*lever/inertia);
    const double rate_p=coeff[1]*2*lever*lever/inertia;
    const double duration=0.8/std::max({rate_n,rate_s,rate_p});
    const std::array<double,3> expected={0.4*std::exp(-rate_n*duration),
        (1+0.5*lever)*std::exp(-rate_s*duration),
        (1.1*lever)*std::exp(-rate_p*duration)};
    for (int i=0;i<steps;++i) nf.apply(b,duration/steps);
    // Centers intentionally stay frozen: this is an exact reduced ODE oracle,
    // not a simulation of a moving wet collision.
    const std::array<double,3> observed={b[0].v.x-b[1].v.x,
        b[0].v.y-b[1].v.y+lever*(b[0].omega+b[1].omega),
        lever*(b[0].omega-b[1].omega)};
    double error=0;
    for (int i=0;i<3;++i) error=std::max(error,std::abs(observed[i]-expected[i]));
    return error;
}

template<class F> bool throws(F&& f) {
    try { f(); } catch (const std::exception&) { return true; }
    return false;
}

} // namespace

int run_near_field_tests() {
    using namespace ibdem;
    std::cout<<std::setprecision(17);
    int failures=0;
    const auto report=[&](const std::string& name,bool passed,const std::string& values) {
        std::cout<<"TEST "<<name<<" "<<(passed?"PASS":"FAIL")<<" "<<values<<"\n";
        failures+=!passed;
    };
    const auto number=[](double x) { std::ostringstream s; s<<std::setprecision(17)<<x; return s.str(); };

    try {
        NearField nf=testLaw();
        Body a=disk(1,{0,0},1,1),b=disk(2,{2.67,0},1.6,1);
        const auto p=nf.pair_resistance(a,b);
        const auto exact=referenceCoefficients(1,1.6,p.gap,nf);
        const double en=std::abs(p.Rn-exact[0])/exact[0],et=std::abs(p.Ct-exact[1])/exact[1];
        report("near_field_coefficients",en<1e-13 && et<1e-13,
               "normal_relative_error="+number(en)+" tangential_relative_error="+number(et)+" Rn="+number(p.Rn)+" Ct="+number(p.Ct));
    } catch (const std::exception& e) { report("near_field_coefficients",false,std::string("exception=")+e.what()); }

    try {
        auto b=mixedBodies();
        b[0].force={1.2,-3}; b[0].torque=0.4;
        const Vec2 fixed_position=b[1].x;
        NearField nf=testLaw();
        nf.apply(b,0.07);
        const auto& s=nf.stats;
        const bool fixed_reaction=norm(nf.impulse[1].linear)>0 &&
            b[1].x.x==fixed_position.x && b[1].x.y==fixed_position.y && norm(b[1].v)==0;
        const bool contact_force_preserved=b[0].force.x==1.2 && b[0].force.y==-3 && b[0].torque==0.4;
        report("near_field_energy_impulse",s.kinetic_after<s.kinetic_before && s.physical_dissipation>0 &&
               s.numerical_dissipation>0 && std::abs(s.energy_residual)<1e-12*(1+s.kinetic_before) &&
               s.linear_balance<1e-12 && s.angular_balance<1e-12 && s.solve_residual<1e-12 &&
               fixed_reaction && contact_force_preserved,
               "physical_dissipation="+number(s.physical_dissipation)+" numerical_dissipation="+number(s.numerical_dissipation)+
               " energy_residual="+number(s.energy_residual)+" linear_balance="+number(s.linear_balance)+
               " angular_balance="+number(s.angular_balance)+" solve_residual="+number(s.solve_residual));
    } catch (const std::exception& e) { report("near_field_energy_impulse",false,std::string("exception=")+e.what()); }

    try {
        std::vector<Body> b={disk(1,{-1.2,0.3},1,1.2),disk(2,{0.8,0.6},0.7,1.4)};
        const Vec2 translation={0.3,-0.2}; const double omega=0.9;
        for (Body& body:b) { body.v=translation+omega*perp(body.x); body.omega=omega; }
        const auto before=b;
        NearField nf=testLaw();
        const auto p=nf.pair_resistance(b[0],b[1]);
        const std::array<double,6> u={b[0].v.x,b[0].v.y,omega,b[1].v.x,b[1].v.y,omega};
        double mode_error=0;
        for (const auto& mode:p.modes) mode_error=std::max(mode_error,std::abs(dot6(mode,u)));
        nf.apply(b,0.5);
        double velocity_error=0;
        for (std::size_t i=0;i<b.size();++i)
            velocity_error=std::max(velocity_error,norm(b[i].v-before[i].v)+std::abs(b[i].omega-before[i].omega));
        report("near_field_rigid_motion_null",mode_error<1e-13 && velocity_error<1e-12 && nf.stats.physical_dissipation<1e-24,
               "mode_error="+number(mode_error)+" velocity_error="+number(velocity_error)+" physical_dissipation="+number(nf.stats.physical_dissipation));
    } catch (const std::exception& e) { report("near_field_rigid_motion_null",false,std::string("exception=")+e.what()); }

    try {
        NearField nf=testLaw();
        Body a=disk(1,{0,0},1,1),b=disk(2,{1.0e8+1.08,0},1.0e8,1,true);
        const auto p=nf.pair_resistance(a,b);
        // Translation along t and rotation of a are columns 1 and 2 here.
        const double ktt=p.Ct*(p.modes[1][1]*p.modes[1][1]+p.modes[2][1]*p.modes[2][1]);
        const double kww=p.Ct*(p.modes[1][2]*p.modes[1][2]+p.modes[2][2]*p.modes[2][2]);
        const double ktw=p.Ct*(p.modes[1][1]*p.modes[1][2]+p.modes[2][1]*p.modes[2][2]);
        const double relative_cross=std::abs(ktw)/std::sqrt(ktt*kww);
        const double translation_error=std::abs(ktt/(2*p.Ct)-1);
        const double rotation_error=std::abs(kww/(2*p.Ct*p.la*p.la)-1);
        report("near_field_wall_cross_cancellation",relative_cross<3e-8 && translation_error<5e-8 && rotation_error<1e-13,
               "relative_translation_rotation_cross="+number(relative_cross)+" wall_translation_error="+number(translation_error)+" wall_rotation_error="+number(rotation_error));
    } catch (const std::exception& e) { report("near_field_wall_cross_cancellation",false,std::string("exception=")+e.what()); }

    try {
        auto b=mixedBodies();
        NearField nf=testLaw();
        const double dt=0.09;
        std::vector<std::size_t> body_index;
        std::vector<int> component;
        std::vector<double> mass,rhs;
        for (std::size_t i=0;i<b.size();++i) if (!b[i].fixed) {
            for (int c=0;c<3;++c) {
                body_index.push_back(i); component.push_back(c);
                const double m=c==2 ? b[i].inertia : b[i].mass;
                const double u=c==0 ? b[i].v.x : (c==1 ? b[i].v.y : b[i].omega);
                mass.push_back(m); rhs.push_back(m*u);
            }
        }
        const std::size_t n=rhs.size();
        std::vector<double> matrix(n*n,0);
        for (std::size_t col=0;col<n;++col) {
            auto probe=b;
            for (Body& body:probe) { body.v={}; body.omega=0; }
            Body& selected=probe[body_index[col]];
            if (component[col]==0) selected.v.x=1;
            else if (component[col]==1) selected.v.y=1;
            else selected.omega=1;
            const auto force=referenceForce(probe,nf);
            for (std::size_t row=0;row<n;++row)
                matrix[row*n+col]=(row==col ? mass[row] : 0)-dt*force[3*body_index[row]+component[row]];
        }
        const auto exact=denseSolve(matrix,rhs);
        nf.apply(b,dt);
        double error=0;
        for (std::size_t i=0;i<n;++i) {
            const Body& body=b[body_index[i]];
            const double observed=component[i]==0 ? body.v.x : (component[i]==1 ? body.v.y : body.omega);
            error=std::max(error,std::abs(observed-exact[i]));
        }
        report("near_field_independent_dense",error<1e-10,"max_velocity_error="+number(error));
    } catch (const std::exception& e) { report("near_field_independent_dense",false,std::string("exception=")+e.what()); }

    try {
        const double a=frozenModalError(20),b=frozenModalError(40),c=frozenModalError(80);
        const double order=std::log(b/c)/std::log(2.0);
        report("near_field_frozen_modal_refinement",a>b && b>c && order>0.9 && order<1.1,
               "error20="+number(a)+" error40="+number(b)+" error80="+number(c)+" observed_order="+number(order));
    } catch (const std::exception& e) { report("near_field_frozen_modal_refinement",false,std::string("exception=")+e.what()); }

    try {
        NearField nf;
        nf.viscosity=0.2; nf.normal_cutoff=0.3; nf.tangential_cutoff=0.2; nf.min_gap=0.02;
        Body a=disk(1,{0,0},1,1),b=disk(2,{2.35,0},1,1);
        const auto outside=nf.pair_resistance(a,b);
        b.x.x=2.2; const auto tangent_edge=nf.pair_resistance(a,b);
        b.x.x=2.005; const auto below=nf.pair_resistance(a,b);
        b.x.x=2.02; const auto at_floor=nf.pair_resistance(a,b);
        const double floor_error=std::abs(below.Rn-at_floor.Rn)/(1+below.Rn)+std::abs(below.Ct-at_floor.Ct)/(1+below.Ct);
        int guarded=0;
        guarded+=throws([&] { auto bad=nf; bad.min_gap=0; bad.pair_resistance(a,b); });
        guarded+=throws([&] { auto bad=nf; bad.normal_cutoff=bad.min_gap; bad.pair_resistance(a,b); });
        guarded+=throws([&] { Body bad=b; bad.x.x=2; nf.pair_resistance(a,bad); });
        guarded+=throws([&] { auto bad=nf; bad.viscosity=-1; bad.pair_resistance(a,b); });
        guarded+=throws([&] { std::vector<Body> x={a,b}; nf.apply(x,-1); });
        nf.enabled=false;
        std::vector<Body> x={a,b}; x[0].v={0.3,-0.2}; x[1].x={1.9,0};
        nf.apply(x,0.5);
        const bool disabled_identity=x[0].v.x==0.3 && x[0].v.y==-0.2 && nf.pair_table.empty() && nf.impulse.size()==2 && norm(nf.impulse[0].linear)==0;
        report("near_field_cutoffs_and_guards",outside.Rn==0 && outside.Ct==0 && tangent_edge.Rn>0 &&
               std::abs(tangent_edge.Ct)<1e-12 && floor_error<1e-12 && guarded==5 && disabled_identity,
               "floor_coefficient_error="+number(floor_error)+" rejected_cases="+std::to_string(guarded)+" disabled_identity="+std::to_string(disabled_identity));
    } catch (const std::exception& e) { report("near_field_cutoffs_and_guards",false,std::string("exception=")+e.what()); }

    return failures;
}
