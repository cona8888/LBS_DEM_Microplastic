#include "film_port.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using ibdem::FilmPortInput;
using ibdem::ReynoldsFilmPort;
namespace {
using Real=long double;
void check(bool ok,const std::string& what) {if(!ok)throw std::runtime_error(what);}
void close(Real a,Real b,Real scale,const std::string& name,Real tol=2e-10L) {
    if(!std::isfinite(a)||!std::isfinite(b)||std::abs(a-b)>tol*std::max({std::abs(a),std::abs(b),scale})) {
        std::cerr<<std::setprecision(18)<<name<<": got "<<a<<", expected "<<b<<"\n";
        throw std::runtime_error(name);
    }
}
template<class F> Real integral(Real lo,Real hi,F f,int n=4096) {
    const Real h=(hi-lo)/n;
    Real sum=f(lo)+f(hi);
    for(int i=1;i<n;++i)sum+=(i%2?4:2)*f(lo+i*h);
    return sum*h/3;
}
FilmPortInput base() {
    FilmPortInput v;
    v.radius_a=1.2e-3; v.radius_b=0.8e-3; v.h=1.5e-6;
    v.half_length=4e-5; v.viscosity=1.1e-3;
    return v;
}
void stationary() {
    auto v=base(); const Real r=1/(1.L/v.radius_a+1.L/v.radius_b);
    const Real h=v.h,L=v.half_length,ell=std::sqrt(2*r*h),z=L/ell,k=1+z*z;
    const Real i3=ell/(h*h*h)*(3*std::atan(z)/4+3*z/(4*k)+z/(2*k*k));
    const Real expected=1/(12*v.viscosity*i3);
    for(double dp:{-140.,0.,140.}) {
        v.pressure_left=1000+dp;v.pressure_right=1000;
        ReynoldsFilmPort p(v);const auto f=p.evaluate();
        close(f.conductance,expected,0,"closed finite-interval conductance",2e-14);
        close(f.center_flux,expected*dp,0,"static flux");
        close(f.outward_left,-expected*dp,0,"left outward sign");
        close(f.outward_right,expected*dp,0,"right outward sign");
        close(f.port_power,expected*dp*dp,0,"static pressure work");
        close(f.dissipation,f.port_power,0,"static passivity");
        close(p.pressure(-v.half_length),v.pressure_left,0,"left pressure");
        close(p.pressure(v.half_length),v.pressure_right,0,"right pressure");
    }
    auto small=v;small.h/=4;small.half_length/=2;
    close(ReynoldsFilmPort(small).evaluate().conductance,expected/32,0,
          "G proportional to h^(5/2) for fixed radius and L/sqrt(2Rh)");
}
void manufactured() {
    auto v=base();v.va_t=.012;v.vb_t=-.007;v.omega_a=18;v.omega_b=-11;
    v.closing_speed=.0002;v.pressure_left=1500;
    const Real a=v.radius_a,b=v.radius_b,L=v.half_length,mu=v.viscosity,vn=v.closing_speed;
    const Real c=(b*v.va_t+a*v.vb_t)/(a+b);
    const Real ua=v.va_t+a*v.omega_a-c,ub=v.vb_t-b*v.omega_b-c;
    const Real q0=2.6e-8L;
    auto H=[&](Real x){return static_cast<Real>(v.h)+x*x*(1/a+1/b)/2;};
    auto Q=[&](Real x){return q0+vn*x;};
    auto grad=[&](Real x){const Real Hx=H(x);return 12*mu*((ua+ub)*Hx/2-Q(x))/(Hx*Hx*Hx);};
    // Manufacture the right boundary pressure by independent quadrature,
    // starting from a specified Q0. No analytic moments from the solver used.
    v.pressure_right=static_cast<double>(v.pressure_left+integral(-L,L,grad));
    const ReynoldsFilmPort p(v);const auto f=p.evaluate();
    close(f.center_flux,q0,0,"manufactured through-flux");
    for(double fraction:{-1.,-.65,0.,.27,.87,1.}) {
        const double x=fraction*v.half_length;
        close(p.gap(x),H(x),0,"manufactured height");
        close(p.flux(x),Q(x),0,"manufactured flux");
        close(p.pressure_gradient(x),grad(x),1,"manufactured gradient");
        close(p.pressure(x),v.pressure_left+integral(-L,x,grad),1,"manufactured pressure");
    }
    auto tau=[&](Real x,Real y){
        return mu*(ub-ua)/H(x)+grad(x)*(y-H(x)/2);
    };
    const Real fa=integral(-L,L,[&](Real x){return -tau(x,0);});
    const Real fb=integral(-L,L,[&](Real x){return tau(x,H(x));});
    const Real pint=2*L*v.pressure_left+integral(-L,L,[&](Real x){return (L-x)*grad(x);});
    const Real shear=ua*fa+ub*fb,squeeze=vn*pint;
    const Real port=v.pressure_left*Q(-L)-v.pressure_right*Q(L);
    // Integrate mu*(du/dy)^2 over the actual film, using two-point Gauss
    // across each section (exact for quadratic shear dissipation).
    const Real diss=integral(-L,L,[&](Real x) {
        const Real hy=H(x)/2, s1=tau(x,hy*(1-1/std::sqrt(3.L))),s2=tau(x,hy*(1+1/std::sqrt(3.L)));
        return hy*(s1*s1+s2*s2)/mu;
    });
    close(f.shear_on_fluid_a,fa,0,"lower wall traction");
    close(f.shear_on_fluid_b,fb,0,"upper wall traction");
    close(f.pressure_integral,pint,0,"squeeze load integral");
    close(f.port_power,port,diss,"port work");close(f.shear_power,shear,diss,"shear work");
    close(f.squeeze_power,squeeze,diss,"pressure work on moving walls");
    close(f.dissipation,diss,0,"independent integrated viscous dissipation");
    close(f.port_power+f.shear_power+f.squeeze_power,diss,0,"all-port power balance");
    // Geometric control-volume derivative, independent of port signs.
    const Real eps=1e-7L;
    auto volume=[&](Real time){return integral(-L,L,[&](Real x){return H(x)-vn*time;},64);};
    const Real vdot=(volume(eps)-volume(-eps))/(2*eps);
    close(f.area,volume(0),0,"film area");close(f.area_rate,vdot,0,"geometric area rate",1e-8);
    close(f.outward_left+f.outward_right,-vdot,0,"moving-volume balance",1e-8);
    check(f.dissipation>=0,"manufactured passivity");
    std::cout<<std::setprecision(12)<<"manufactured SI: G="<<f.conductance
             <<" Qleft_out="<<f.outward_left<<" Qright_out="<<f.outward_right
             <<" D="<<f.dissipation<<" W/m; energy residual="<<f.power_residual<<"\n";
}
void invariance_and_scaling() {
    auto v=base();v.va_t=.006;v.vb_t=-.003;v.omega_a=-.8;v.omega_b=2.2;
    v.closing_speed=-.0007;v.pressure_left=3700;v.pressure_right=4010;
    const ReynoldsFilmPort p(v);const auto f=p.evaluate();
    auto shift=v;shift.va_t+=2;shift.vb_t+=2;shift.pressure_left+=18300;shift.pressure_right+=18300;
    const ReynoldsFilmPort shifted(shift);const auto q=shifted.evaluate();
    close(q.gap_frame_velocity-f.gap_frame_velocity,2,0,"translating frame");
    close(q.center_flux,f.center_flux,0,"Galilean and pressure-gauge invariant relative flux");
    close(q.port_power-f.port_power,18300*f.area_rate,0,"port gauge work");
    close(q.squeeze_power-f.squeeze_power,-18300*f.area_rate,0,"wall gauge work");
    close(q.total_power_in,f.total_power_in,0,"gauge-invariant power");
    close(shifted.pressure(0)-p.pressure(0),18300,0,"pressure reference shift");
    // Lengths x lambda, velocities x sigma, mu x gamma, pressure x gamma*sigma/lambda.
    const double lambda=1e3,sigma=.7,gamma=3.2,ps=gamma*sigma/lambda;
    auto scaled=v;scaled.radius_a*=lambda;scaled.radius_b*=lambda;scaled.h*=lambda;
    scaled.half_length*=lambda;scaled.va_t*=sigma;scaled.vb_t*=sigma;
    scaled.omega_a*=sigma/lambda;scaled.omega_b*=sigma/lambda;scaled.closing_speed*=sigma;
    scaled.viscosity*=gamma;scaled.pressure_left*=ps;scaled.pressure_right*=ps;
    const ReynoldsFilmPort sc(scaled);const auto z=sc.evaluate();
    close(z.conductance,f.conductance*lambda*lambda/gamma,0,"dimensional conductance scaling");
    close(z.outward_right,f.outward_right*lambda*sigma,0,"dimensional volume-flux scaling");
    close(z.pressure_integral,f.pressure_integral*gamma*sigma,0,"force-per-length scaling");
    close(z.dissipation,f.dissipation*gamma*sigma*sigma,0,"power-per-length scaling");
    close(sc.pressure(0),p.pressure(0)*ps,0,"pressure scaling");
}
void limiting_modes() {
    auto v=base();v.omega_a=.002/v.radius_a;v.omega_b=.002/v.radius_b;
    const auto f=ReynoldsFilmPort(v).evaluate();
    const Real r=1/(1.L/v.radius_a+1.L/v.radius_b),ell=std::sqrt(2*r*v.h);
    const Real i1=2*ell/v.h*std::atan(v.half_length/ell);
    close(f.dissipation, .004L*.004L*v.viscosity*i1,0,"pure antisymmetric wall shear");
    close(f.dissipation_pressure,0,f.dissipation,"zero pressure dissipation for pure shear");
    auto narrow=base();narrow.half_length=1e-4*ell;narrow.pressure_left=1;
    const auto z=ReynoldsFilmPort(narrow).evaluate();
    close(z.conductance,std::pow(static_cast<Real>(narrow.h),3)/(24*narrow.viscosity*narrow.half_length),
          0,"short-port parallel-plate conductance",2e-8);
    // No slip, pure tangential entrainment, almost uniform gap: dissipation
    // is small and positive; a subtraction of large I1,I2^2/I3 can lose it.
    narrow.pressure_left=0;narrow.omega_a=.002/narrow.radius_a;narrow.omega_b=-.002/narrow.radius_b;
    const auto en=ReynoldsFilmPort(narrow).evaluate();
    check(en.dissipation_pressure>0,"short-interval entrainment dissipation");
    const Real T=narrow.half_length/ell;
    close(en.dissipation_pressure,12*narrow.viscosity*.002L*.002L*2*ell/narrow.h*
          (4.L/45)*std::pow(T,5),0,"short-interval analytic entrainment asymptote",1e-7);
}
void invalid_inputs() {
    for(int k=0;k<5;++k) {
        auto v=base();
        if(k==0)v.h=0;
        if(k==1)v.viscosity=-1;
        if(k==2)v.half_length=0;
        if(k==3)v.radius_b=std::numeric_limits<double>::infinity();
        if(k==4)v.pressure_right=std::numeric_limits<double>::quiet_NaN();
        bool caught=false;try{ReynoldsFilmPort rejected(v);}catch(const std::invalid_argument&){caught=true;}
        check(caught,"invalid state rejected");
    }
    const auto v=base();const ReynoldsFilmPort p(v);
    bool caught=false;try{p.pressure(v.half_length*1.001);}catch(const std::out_of_range&){caught=true;}
    check(caught,"out-of-interval pressure sample rejected");
}
}
int main() {
    try {
        stationary();manufactured();invariance_and_scaling();limiting_modes();invalid_inputs();
        std::cout<<"PASS: 5 film-port test groups (conductance, manufactured fields/work/volume, "
                   "invariance/scaling, limiting modes, domain checks).\n";return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}
}
