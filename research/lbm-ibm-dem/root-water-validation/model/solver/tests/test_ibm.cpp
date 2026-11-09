#include "ibm.hpp"
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <stdexcept>
#include <limits>

using namespace ibdem;
namespace {
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
Vec2 fluid_p(const LBM& f){Vec2 p;for(int i=0;i<f.n;++i)p+=f.u[i]*f.rho[i];return p;}
double fluid_l(const LBM& f){double l=0;for(int i=0;i<f.n;++i)l+=cross({double(i%f.nx),double(i/f.nx)},f.u[i]*f.rho[i]);return l;}
std::pair<Vec2,double> physical(const LBM& f,const std::vector<Body>& b,const IBM& ib){Vec2 p=fluid_p(f);double l=fluid_l(f);for(size_t i=0;i<b.size();++i){p+=b[i].v*b[i].mass-ib.old_interior[i].p;l+=cross(b[i].x,b[i].v*b[i].mass)+b[i].inertia*b[i].omega-ib.old_interior[i].angular;}return {p,l};}
template<class F> void test(const char* name,F fn,int& fail){try{fn();std::cout<<"PASS "<<name<<"\n";}catch(const std::exception& e){++fail;std::cout<<"FAIL "<<name<<": "<<e.what()<<"\n";}}
}
int run_ibm_tests(){
 int fail=0;
 test("ibm_kernel_moments_and_disk_volume",[]{
    for(double x:{10.01,10.23,10.5,10.97}){double s=0,m=0;for(int j=7;j<=14;++j){double w=IBM::kernel(j-x);s+=w;m+=(j-x)*w;}require(std::abs(s-1)<1e-14&&std::abs(m)<1e-14,"Kernel moments failed");}
    for(Vec2 c:std::vector<Vec2>{{15.1,16.3},{15.5,16.5},{15.99,16.01}}){double area=0;for(int y=0;y<32;++y)for(int x=0;x<32;++x)area+=IBM::disk_cell_area(c,5.3,x,y);require(std::abs(area-pi*5.3*5.3)<3e-12,"Disk overlap areas do not sum to exact volume");}
 },fail);
 test("ibm_adjoint_work_and_first_moment",[]{
    LBM f(64,48);std::vector<Body>b{disk(0,{20.3,21.7},6,1.1),disk(1,{34.0,23.0},6,1.2)};IBM ib;ib.initialize(f,b);
    std::vector<Vec2> u(f.n),s(f.n);for(int i=0;i<f.n;++i)u[i]={std::sin(i*.71),std::cos(i*.53)};double markerwork=0;Vec2 net;double torque=0;
    for(size_t m=0;m<ib.markers.size();++m){const auto&a=ib.markers[m];Vec2 l{std::sin(m*.37),std::cos(m*.61)},v;for(int k=0;k<16;++k){v+=u[a.node[k]]*a.w[k];s[a.node[k]]+=l*a.w[k];}markerwork+=dot(v,l);net+=l;torque+=cross(a.x,l);}
    double gridwork=0,gridtorque=0;Vec2 gridnet;for(int i=0;i<f.n;++i){gridwork+=dot(u[i],s[i]);gridnet+=s[i];gridtorque+=cross({double(i%f.nx),double(i/f.nx)},s[i]);}
    require(std::abs(gridwork-markerwork)<1e-12,"Adjoint work failure");require(norm(gridnet-net)<1e-12,"Linear impulse failure");require(std::abs(gridtorque-torque)<1e-10,"Angular impulse failure");
 },fail);
 test("ibm_dense_compact_fullgrid_operator_equivalence",[]{
    LBM f(64,48);std::vector<Body>b{disk(0,{20.3,21.7},6,0.8),disk(1,{33.0,22.0},6,1.2)};b[1].fixed=true;IBM ib;ib.initialize(f,b);int n=2*ib.markers.size();std::vector<double>x(n);for(int i=0;i<n;++i)x[i]=std::sin(i*.77);
    auto compact=ib.apply_operator(f,b,x,true),full=ib.apply_operator(f,b,x,false);double error=0;for(int i=0;i<n;++i){double dense=0;for(int j=0;j<n;++j)dense+=ib.operator_entry(f,b,i,j)*x[j];error=std::max({error,std::abs(compact[i]-dense),std::abs(compact[i]-full[i])});}require(error<2e-14,"Three operator realizations disagree");
 },fail);
 test("ibm_two_way_physical_linear_and_angular_impulse",[]{
    LBM f(64,48);std::vector<Body>b{disk(0,{22.3,23.1},6,0.9)};b[0].v={.025,-.012};b[0].omega=.001;IBM ib;ib.relative_tolerance=1e-12;ib.initialize(f,b);auto before=physical(f,b,ib);Vec2 initialfluid=fluid_p(f),initialparticle=b[0].v;ib.couple(f,b);auto after=physical(f,b,ib);
    require(norm(after.first-before.first)<2e-11,"Physical linear momentum changed");require(std::abs(after.second-before.second)<2e-9,"Physical angular momentum changed");require(norm(fluid_p(f)-initialfluid)>1e-4&&norm(b[0].v-initialparticle)>1e-5,"Missing one side of two-way response");require(ib.stats.max_slip<2e-11,"No-slip residual too large");
    std::cout<<"METRIC impulse_linear_error="<<norm(after.first-before.first)<<" impulse_angular_error="<<std::abs(after.second-before.second)<<" max_slip="<<ib.stats.max_slip<<"\n";
 },fail);
 test("ibm_moving_light_neutral_dense_particles_80_steps",[]{
    for(double density:{0.5,0.8,1.0,2.5}){LBM f(64,48);std::vector<Body>b{disk(0,{25.3,24.7},6,density)};b[0].v={.008,-.003};b[0].omega=.0002;IBM ib;ib.relative_tolerance=2e-11;ib.initialize(f,b);auto before=physical(f,b,ib);double slip=0,maxu=0;
        for(int t=0;t<80;++t){b[0].x+=b[0].v;b[0].angle+=b[0].omega;f.collide_stream();ib.couple(f,b);slip=std::max(slip,ib.stats.max_slip);for(auto u:f.u)maxu=std::max(maxu,norm(u));}
        auto after=physical(f,b,ib);require(norm(after.first-before.first)<2e-9,"Moving-volume momentum balance failed");require(slip<1e-10&&maxu<.1,"Short-run density/motion smoke test failed");std::cout<<"METRIC density="<<density<<" momentum_drift="<<norm(after.first-before.first)<<" max_slip="<<slip<<" peak_fluid_speed="<<maxu<<"\n";
    }
 },fail);
 test("ibm_reference_vs_cached_same_equations_40_steps",[]{
    LBM f(72,56),g(72,56);f.initialize({.008,0});g.initialize({.008,0});std::vector<Body>b{disk(0,{25.3,27.1},6,1.1),disk(1,{38.5,27.5},6,1.3,true)},c=b;IBM ref(IBM::Mode::Reference),fast;ref.relative_tolerance=fast.relative_tolerance=1e-11;ref.initialize(f,b);fast.initialize(g,c);
    for(int t=0;t<40;++t){for(auto&p:b)if(!p.fixed){p.x+=p.v;p.angle+=p.omega;}for(auto&p:c)if(!p.fixed){p.x+=p.v;p.angle+=p.omega;}f.collide_stream();g.collide_stream();ref.couple(f,b);fast.couple(g,c);}
    double err=0;for(size_t i=0;i<f.f.size();++i)err=std::max(err,std::abs(f.f[i]-g.f[i]));for(size_t i=0;i<b.size();++i)err=std::max({err,norm(b[i].x-c[i].x),norm(b[i].v-c[i].v),std::abs(b[i].omega-c[i].omega)});require(err<2e-9,"Acceleration changes current discrete solution");std::cout<<"METRIC trajectory_population_max_difference="<<err<<"\n";
 },fail);
 test("ibm_rejects_unsupported_wet_overlap",[]{LBM f(48,40);std::vector<Body>b{disk(0,{17,20},5,1),disk(1,{25,20},5,1)};IBM ib;bool rejected=false;try{ib.initialize(f,b);}catch(const std::runtime_error&){rejected=true;}require(rejected,"Wet overlap must not silently produce a result");},fail);
 test("ibm_nonfinite_input_and_iteration_failure",[]{
    LBM f(48,40);std::vector<Body>b{disk(0,{20,20},5,1)};b[0].x.x=std::numeric_limits<double>::quiet_NaN();IBM bad;bool rejected=false;try{bad.initialize(f,b);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"Nonfinite position accepted");
    b[0].x.x=20;b[0].v={.01,0};IBM stalled;stalled.initialize(f,b);stalled.max_iterations=0;rejected=false;try{stalled.couple(f,b);}catch(const std::runtime_error&){rejected=true;}require(rejected,"Unconverged IBM stage accepted");
 },fail);
 test("ibm_uniform_comoving_translation_50_steps",[]{
    LBM f(64,48);Vec2 v{.01,.003};f.initialize(v);std::vector<Body>b{disk(0,{24.3,23.7},5.3,.8)};b[0].v=v;IBM ib;ib.initialize(f,b);
    for(int t=0;t<50;++t){b[0].x+=b[0].v;b[0].angle+=b[0].omega;f.collide_stream();ib.couple(f,b);}
    double translation_error=norm(b[0].v-v);require(translation_error<2e-12&&std::abs(b[0].omega)<2e-12,"Moving overlap quadrature generates spurious motion in uniform comoving flow");
    std::cout<<"METRIC comoving_velocity_error="<<translation_error<<" comoving_spin="<<b[0].omega<<"\n";
 },fail);
 return fail;
}
