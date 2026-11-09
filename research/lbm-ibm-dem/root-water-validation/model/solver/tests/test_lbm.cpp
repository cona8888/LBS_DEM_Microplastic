#include "lbm.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using ibdem::LBM;
using ibdem::Vec2;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

void close(double actual, double expected, double tolerance, const std::string& label) {
    if (!std::isfinite(actual) || std::abs(actual-expected) > tolerance) {
        std::ostringstream message;
        message.precision(17);
        message << label << ": actual=" << actual << ", expected=" << expected
                << ", tolerance=" << tolerance;
        throw std::runtime_error(message.str());
    }
}

struct Moments { long double mass=0.0L, px=0.0L, py=0.0L; };

Moments population_moments(const LBM& lattice) {
    Moments result;
    for (int q=0; q<LBM::q_count; ++q) {
        for (int i=0; i<lattice.n; ++i) {
            const long double value=lattice.f[static_cast<std::size_t>(q)*lattice.n+i];
            result.mass+=value;
            result.px+=value*LBM::cx[q];
            result.py+=value*LBM::cy[q];
        }
    }
    return result;
}

long double population_angular_momentum(const LBM& lattice) {
    long double result=0.0L;
    for (int q=0; q<LBM::q_count; ++q) {
        for (int y=0; y<lattice.ny; ++y) for (int x=0; x<lattice.nx; ++x) {
            const long double value=lattice.f[static_cast<std::size_t>(q)*lattice.n+y*lattice.nx+x];
            result+=(static_cast<long double>(x)*LBM::cy[q]-static_cast<long double>(y)*LBM::cx[q])*value;
        }
    }
    return result;
}

void test_parameters() {
    for (double tau : {0.5, 0.0, -1.0, std::numeric_limits<double>::infinity(),
                       std::numeric_limits<double>::quiet_NaN()}) {
        bool rejected=false;
        try { LBM lattice(8,8,tau); } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected,"Invalid tau_plus was accepted");
    }
    bool rejected=false;
    try { LBM lattice(0,8); } catch (const std::invalid_argument&) { rejected=true; }
    require(rejected,"Zero dimension was accepted");
    rejected=false;
    try { LBM lattice(8,8,0.8,-1.0); } catch (const std::invalid_argument&) { rejected=true; }
    require(rejected,"Negative TRT magic was accepted");
    LBM lattice(8,8);
    close((lattice.tau_plus-0.5)*(lattice.tau_minus-0.5),3.0/16.0,1e-15,"TRT relation");
}

void test_equilibrium_rest() {
    LBM lattice(17,13);
    const auto initial=lattice.f;
    for (int step=0; step<25; ++step) lattice.collide_stream();
    for (std::size_t i=0; i<initial.size(); ++i) {
        close(lattice.f[i],initial[i],2e-14,"Rest equilibrium population");
    }
    for (int i=0; i<lattice.n; ++i) {
        close(lattice.rho[i],1.0,2e-14,"Rest density");
        close(ibdem::norm(lattice.u[i]),0.0,2e-14,"Rest velocity");
    }
}

void test_uniform_translation() {
    // Large enough to exercise the OpenMP path when compiled with -fopenmp.
    LBM lattice(128,128,0.71);
    const Vec2 velocity{0.023,-0.017};
    lattice.initialize(velocity,1.13);
    const auto initial=lattice.f;
    for (int step=0; step<12; ++step) lattice.collide_stream();
    for (std::size_t i=0; i<initial.size(); ++i) {
        close(lattice.f[i],initial[i],3e-14,"Uniform periodic population");
    }
    for (int i=0; i<lattice.n; ++i) {
        close(lattice.u[i].x,velocity.x,3e-14,"Uniform ux");
        close(lattice.u[i].y,velocity.y,3e-14,"Uniform uy");
    }
}

void test_global_conservation() {
    LBM lattice(31,23,0.92);
    std::vector<Vec2> velocity(lattice.n);
    for (int y=0; y<lattice.ny; ++y) for (int x=0; x<lattice.nx; ++x) {
        velocity[y*lattice.nx+x]={0.011+0.006*std::sin(2.0*ibdem::pi*y/lattice.ny),
                                 -0.007+0.004*std::cos(2.0*ibdem::pi*x/lattice.nx)};
    }
    lattice.initialize(velocity);
    const auto before=population_moments(lattice);
    for (int step=0; step<100; ++step) lattice.collide_stream();
    const auto after=population_moments(lattice);
    close(static_cast<double>(after.mass-before.mass),0.0,2e-10,"Periodic global mass");
    close(static_cast<double>(after.px-before.px),0.0,2e-11,"Periodic global px");
    close(static_cast<double>(after.py-before.py),0.0,2e-11,"Periodic global py");
}

void test_periodic_angular_flux() {
    // Rectangular geometry makes the two angular shifts at a diagonal corner
    // unequal. Nonuniform populations avoid a cancellation-only equilibrium
    // test, and a zero-momentum shear-stress perturbation exercises collision.
    LBM lattice(19,11,0.87);
    for (int y=0; y<lattice.ny; ++y) for (int x=0; x<lattice.nx; ++x) {
        const int cell=y*lattice.nx+x;
        const Vec2 velocity{.01+.004*std::sin(.37*x+.29*y),
                            -.005+.003*std::cos(.41*x-.17*y)};
        const auto eq=LBM::equilibrium(1.0+.03*std::sin(.19*x+.31*y),velocity);
        for (int q=0; q<LBM::q_count; ++q)
            lattice.f[static_cast<std::size_t>(q)*lattice.n+cell]=eq[q];
        const double shear=1e-4*std::sin(.23*x+.47*y+.3);
        for (int q : {5,7}) lattice.f[static_cast<std::size_t>(q)*lattice.n+cell]+=shear;
        for (int q : {6,8}) lattice.f[static_cast<std::size_t>(q)*lattice.n+cell]-=shear;
    }
    // Distinct diagonal corner packets exercise both wrap signs and the
    // simultaneous x/y contribution without using the diagnostic's formula.
    lattice.f[std::size_t(5)*lattice.n+(lattice.ny-1)*lattice.nx+lattice.nx-1]+=.003;
    lattice.f[std::size_t(6)*lattice.n+(lattice.ny-1)*lattice.nx]+=.002;
    lattice.f[std::size_t(7)*lattice.n]+=.004;
    lattice.f[std::size_t(8)*lattice.n+lattice.nx-1]+=.001;
    lattice.macros();
    const long double initial=population_angular_momentum(lattice);
    long double accumulated_flux=0.0L;
    double largest_flux=0.0,largest_error=0.0;
    for (int step=0; step<12; ++step) {
        const long double before=population_angular_momentum(lattice);
        lattice.collide_stream();
        const double flux=lattice.periodic_angular_flux();
        const long double actual=population_angular_momentum(lattice)-before;
        const double error=std::abs(static_cast<double>(actual)-flux);
        largest_flux=std::max(largest_flux,std::abs(flux));largest_error=std::max(largest_error,error);
        close(flux,static_cast<double>(actual),3e-12,"Independent angular change versus wrap flux");
        accumulated_flux+=flux;
    }
    require(largest_flux>1e-3,"Angular-flux test did not exercise a nonzero wrap budget");
    close(static_cast<double>(population_angular_momentum(lattice)-initial-accumulated_flux),0.0,1e-11,"Accumulated periodic angular budget");
    std::cout<<"  periodic angular flux: max_flux="<<largest_flux<<" max_independent_error="<<largest_error<<'\n';
}

void test_full_equilibrium_impulse() {
    LBM lattice(19,11,0.83);
    lattice.initialize({0.017,-0.012},1.21);
    std::vector<Vec2> impulse(lattice.n);
    long double jx=0.0L,jy=0.0L;
    for (int i=0; i<lattice.n; ++i) {
        impulse[i]={0.004*std::sin(0.7*i)+0.001,-0.003*std::cos(0.4*i)};
        jx+=impulse[i].x;
        jy+=impulse[i].y;
    }
    const auto before=population_moments(lattice);
    const auto original=lattice.f;
    const auto old_velocity=lattice.u;
    lattice.apply_impulse(impulse);
    for (int i=0; i<lattice.n; ++i) {
        double old_mass=0.0,new_mass=0.0,old_px=0.0,new_px=0.0,old_py=0.0,new_py=0.0;
        double old_pxx=0.0,new_pxx=0.0,old_pxy=0.0,new_pxy=0.0,old_pyy=0.0,new_pyy=0.0;
        for (int q=0; q<LBM::q_count; ++q) {
            const auto offset=static_cast<std::size_t>(q)*lattice.n+i;
            const double a=original[offset],b=lattice.f[offset];
            old_mass+=a; new_mass+=b;
            old_px+=LBM::cx[q]*a; new_px+=LBM::cx[q]*b;
            old_py+=LBM::cy[q]*a; new_py+=LBM::cy[q]*b;
            old_pxx+=LBM::cx[q]*LBM::cx[q]*a; new_pxx+=LBM::cx[q]*LBM::cx[q]*b;
            old_pxy+=LBM::cx[q]*LBM::cy[q]*a; new_pxy+=LBM::cx[q]*LBM::cy[q]*b;
            old_pyy+=LBM::cy[q]*LBM::cy[q]*a; new_pyy+=LBM::cy[q]*LBM::cy[q]*b;
        }
        close(new_mass-old_mass,0.0,8e-16,"Impulse local mass");
        close(new_px-old_px,impulse[i].x,2e-16,"Impulse local px");
        close(new_py-old_py,impulse[i].y,2e-16,"Impulse local py");
        const double r=lattice.rho[i];
        const Vec2 a=old_velocity[i],b=a+impulse[i]/r;
        // These second-moment checks detect a merely linear momentum kick:
        // the full equilibrium difference must include terms quadratic in J.
        close(new_pxx-old_pxx,r*(b.x*b.x-a.x*a.x),3e-16,"Impulse quadratic xx");
        close(new_pxy-old_pxy,r*(b.x*b.y-a.x*a.y),2e-16,"Impulse quadratic xy");
        close(new_pyy-old_pyy,r*(b.y*b.y-a.y*a.y),3e-16,"Impulse quadratic yy");
    }
    const auto after=population_moments(lattice);
    close(static_cast<double>(after.mass-before.mass),0.0,3e-13,"Impulse global mass");
    close(static_cast<double>(after.px-before.px-jx),0.0,2e-14,"Impulse global px");
    close(static_cast<double>(after.py-before.py-jy),0.0,2e-14,"Impulse global py");
    const auto cached=lattice.u;
    lattice.macros();
    for (int i=0; i<lattice.n; ++i) {
        close(lattice.u[i].x,cached[i].x,2e-16,"Impulse cached ux");
        close(lattice.u[i].y,cached[i].y,2e-16,"Impulse cached uy");
    }
    for (int step=0; step<50; ++step) lattice.collide_stream();
    const auto evolved=population_moments(lattice);
    close(static_cast<double>(evolved.px-before.px-jx),0.0,2e-12,"Impulse evolved px");
    close(static_cast<double>(evolved.py-before.py-jy),0.0,2e-12,"Impulse evolved py");
}

double shear_amplitude(const LBM& lattice) {
    long double amplitude=0.0L;
    for (int y=0; y<lattice.ny; ++y) {
        const double mode=std::sin(2.0*ibdem::pi*y/lattice.ny);
        for (int x=0; x<lattice.nx; ++x) amplitude+=lattice.u[y*lattice.nx+x].x*mode;
    }
    return static_cast<double>(2.0L*amplitude/lattice.n);
}

void test_shear_wave_viscosity() {
    LBM lattice(16,64,0.8);
    constexpr double amplitude=1e-3;
    std::vector<Vec2> velocity(lattice.n);
    for (int y=0; y<lattice.ny; ++y) for (int x=0; x<lattice.nx; ++x) {
        velocity[y*lattice.nx+x]={amplitude*std::sin(2.0*ibdem::pi*y/lattice.ny),0.0};
    }
    lattice.initialize(velocity);
    // Discard the kinetic startup transient of an equilibrium initialization.
    for (int step=0; step<20; ++step) lattice.collide_stream();
    const double a0=shear_amplitude(lattice);
    constexpr int steps=200;
    for (int step=0; step<steps; ++step) lattice.collide_stream();
    const double a1=shear_amplitude(lattice);
    const double k=2.0*ibdem::pi/lattice.ny;
    const double expected=a0*std::exp(-lattice.viscosity()*k*k*steps);
    const double measured=-std::log(a1/a0)/(k*k*steps);
    close(a1,expected,0.002*std::abs(expected),"Analytic shear-wave amplitude");
    close(measured,lattice.viscosity(),0.005*lattice.viscosity(),"Measured shear-wave viscosity");
    double transverse=0.0;
    for (Vec2 v:lattice.u) transverse=std::max(transverse,std::abs(v.y));
    close(transverse,0.0,2e-13,"Shear-wave transverse flow");
    std::cout << "  shear viscosity: measured=" << measured
              << " analytic=" << lattice.viscosity() << '\n';
}

} // namespace

int run_lbm_tests() {
    struct Test { const char* name; void (*run)(); };
    const Test tests[]{
        {"LBM parameter validation",test_parameters},
        {"LBM rest equilibrium",test_equilibrium_rest},
        {"LBM uniform periodic translation",test_uniform_translation},
        {"LBM global conservation",test_global_conservation},
        {"LBM periodic angular wrap flux",test_periodic_angular_flux},
        {"LBM full equilibrium impulse",test_full_equilibrium_impulse},
        {"LBM analytic shear-wave decay",test_shear_wave_viscosity}
    };
    int failures=0;
    for (const Test& test:tests) {
        try {
            test.run();
            std::cout << "PASS " << test.name << '\n';
        } catch (const std::exception& error) {
            ++failures;
            std::cerr << "FAIL " << test.name << ": " << error.what() << '\n';
        }
    }
    return failures;
}

#ifdef IBDEM_LBM_TEST_MAIN
int main() { return run_lbm_tests(); }
#endif
