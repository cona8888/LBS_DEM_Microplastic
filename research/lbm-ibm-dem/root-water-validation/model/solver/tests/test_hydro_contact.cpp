#include "hydro_contact_step.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

// Standalone tests for the iterated exchange. The reference recoil uses
// prescribed IBM reactions and a scalar bracketed solve, not the production
// free-body IBM operator or the outer iteration. Momentum is reconstructed
// from populations and geometric cell moments, not the solver's audit fields.
namespace {
using namespace ibdem;
void insist(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
struct Budget { long double x=0,y=0,l=0,m=0; };
Budget population_budget(const LBM& f,const std::vector<Body>& b){
    Budget q;
    for(int y=0;y<f.ny;++y)for(int x=0;x<f.nx;++x){
        long double jx=0,jy=0,rho=0;
        for(int c=0;c<LBM::q_count;++c){
            const double fc=f.f[std::size_t(c)*f.n+y*f.nx+x];
            rho+=fc;jx+=fc*LBM::cx[c];jy+=fc*LBM::cy[c];
        }
        double area=1.;Vec2 first{double(x),double(y)};
        for(const auto& p:b){const auto z=disk_cell_moments(p.x,p.radius,x,y);area-=z.area;first-=z.first;}
        q.x+=area*jx;q.y+=area*jy;q.l+=first.x*jy-first.y*jx;
        q.m+=rho; // All-grid LBM mass, distinct from exterior-fluid momentum.
    }
    for(const auto& p:b){
        const auto j=p.v*p.mass;
        q.x+=j.x;q.y+=j.y;q.l+=cross(p.x,j)+p.inertia*p.omega;
    }return q;
}
double marker_slip(const LBM& f,const IBM& ib,const std::vector<Body>& b){
    double worst=0;
    for(const auto& marker:ib.markers){
        Vec2 sampled;
        for(int z=0;z<16;++z){
            const int i=marker.node[z];Vec2 j;double rho=0;
            for(int c=0;c<LBM::q_count;++c){
                const double v=f.f[std::size_t(c)*f.n+i];rho+=v;
                j+=Vec2(double(LBM::cx[c]),double(LBM::cy[c]))*v;
            }sampled+=(j/rho)*marker.w[z];
        }
        const auto& p=b.at(marker.body);
        const Vec2 surface=p.fixed?Vec2{}:(p.v+perp(marker.x-p.x)*p.omega);
        worst=std::max(worst,norm(sampled-surface));
    }return worst;
}
double body_error(const std::vector<Body>& a,const std::vector<Body>& b){
    if(a.size()!=b.size())return INFINITY;
    double e=0;
    for(std::size_t i=0;i<a.size();++i){
        const auto& p=a[i];const auto& q=b[i];
        if(p.id!=q.id||p.fixed!=q.fixed)return INFINITY;
        e=std::max({e,norm(p.x-q.x),norm(p.v-q.v),std::abs(p.angle-q.angle),
           std::abs(p.omega-q.omega),norm(p.force-q.force),std::abs(p.torque-q.torque),
           std::abs(p.mass-q.mass),std::abs(p.inertia-q.inertia),
           std::abs(p.radius-q.radius),std::abs(p.contact_offset-q.contact_offset)});
    }return e;
}
double pop_error(const LBM& f,const LBM& g){
    double e=0;for(std::size_t i=0;i<f.f.size();++i)e=std::max(e,std::abs(f.f[i]-g.f[i]));return e;
}
HydroContactControls controls(){
    HydroContactControls ctl;ctl.max_iterations=70;ctl.relative_tolerance=1e-9;
    ctl.absolute_tolerance=2e-13;ctl.relaxation=1.;return ctl;
}
void inner(IBM& ib){ib.relative_tolerance=1e-12;ib.absolute_tolerance=1e-14;ib.max_iterations=1000;ib.restart=100;}

void recoil_oracle(){
    LBM f(44,32);f.initialize();
    std::vector<Body> b{disk(31,{20.2,16.},3.5,1.2)};
    b[0].v={0.017,0.};const auto b0=b;
    IBM ib;inner(ib);ib.initialize(f,b);
    DEM dem;NearField near;near.enabled=false;
    LBM predictor(f);predictor.collide_stream();
    // Reflection leaves a scalar recoil along the x-axis. Without contact,
    // symmetric half-kicks give x1=x0+(v0+v1)/2 at the outer fixed point.
    // Impose the proposed v1 using the *prescribed* solver at that position.
    // A free disk requires m(v1-v0) to equal the resulting physical reaction.
    const auto balance=[&](double v1){
        auto bb=b0;IBM op(IBM::Mode::Reference);inner(op);op.initialize(f,bb);
        bb[0].x.x+=.5*(b0[0].v.x+v1);bb[0].v={v1,0};
        LBM trial(predictor);op.couple_prescribed(trial,bb);
        return b0[0].mass*(v1-b0[0].v.x)-op.hydrodynamic_impulse.at(0).linear.x;
    };
    double lo=0.,hi=b0[0].v.x;
    insist(balance(lo)<0.&&balance(hi)>0.,"prescribed-reaction root is not bracketed");
    for(int k=0;k<38;++k){const double mid=.5*(lo+hi);if(balance(mid)>0.)hi=mid;else lo=mid;}
    const double oracle=.5*(lo+hi);
    const auto initial=population_budget(f,b);
    const auto out=advance_hydro_contact_iterated(f,ib,dem,near,b,4,controls());
    const auto final=population_budget(f,b);
    const auto& j=ib.hydrodynamic_impulse.at(0);
    const double ve=std::abs(b[0].v.x-oracle);
    const double xe=std::abs(b[0].x.x-b0[0].x.x-.5*(b0[0].v.x+oracle));
    const double impulse=norm((b[0].v-b0[0].v)*b[0].mass-j.linear);
    const double angular=std::abs(cross(b[0].x,b[0].v*b[0].mass)+b[0].inertia*b[0].omega
        -cross(b0[0].x,b0[0].v*b0[0].mass)-b0[0].inertia*b0[0].omega-j.angular);
    const double pe=double(std::hypot(final.x-initial.x,final.y-initial.y));
    const double le=double(std::abs(final.l-initial.l));
    const double slip=marker_slip(f,ib,b);
    insist(out.outer_iterations>1&&std::abs(j.linear.x)>.03,"nontrivial recoil/outer iteration was not exercised");
    insist(ve<5e-10&&xe<5e-10&&std::abs(b[0].v.y)<1e-11&&std::abs(b[0].omega)<1e-11,
           "coupled free recoil disagrees with prescribed-reaction fixed point");
    insist(impulse<2e-10&&angular<2e-9&&pe<3e-10&&le<5e-9&&slip<2e-11,
           "recoil momentum, global angular impulse or endpoint no slip failed");
    std::cout<<"METRIC recoil_oracle_v="<<oracle<<" velocity_error="<<ve<<" drift_error="<<xe
             <<" one_impulse_error="<<impulse<<" angular_impulse_error="<<angular
             <<" physical_p_error="<<pe<<" physical_l_error="<<le<<" marker_slip="<<slip
             <<" outer="<<out.outer_iterations<<'\n';
}

struct Fixture {
    LBM f{48,40};IBM ib;DEM dem;NearField near;std::vector<Body> b;
    Fixture(){
        std::vector<Vec2> u(f.n);for(int y=0;y<f.ny;++y)for(int x=0;x<f.nx;++x)
            u[y*f.nx+x]={.004*std::sin(2*pi*(y+.2)/f.ny),.002*std::cos(2*pi*(x+.4)/f.nx)};
        f.initialize(u);
        b={disk(9,{19.2,18.6},3.4,1.10,false,.40),
           disk(2,{26.47,19.26},3.4,1.45,false,.40)};
        b[0].v={.010,.008};b[1].v={-.008,-.003};b[0].omega=.0012;b[1].omega=-.0003;
        dem.kn=.18;dem.kt=.12;dem.cn=.025;dem.ct=.005;dem.mu=.75;
        dem.evaluate(b,.25); // Nonzero prior sticking history, included in every trial.
        near.enabled=true;near.viscosity=.025;near.normal_cutoff=1.2;near.tangential_cutoff=1.1;near.min_gap=.1;
        auto diagnostic_bodies=b;near.apply(diagnostic_bodies,.125);
        inner(ib);ib.marker_retraction=.20;ib.initialize(f,b);
    }
};
void replay_kick(std::vector<Body>& b,const std::vector<HydrodynamicImpulse>& js,double fraction){
    for(std::size_t i=0;i<b.size();++i)if(!b[i].fixed){
        const Vec2 dp=js[i].linear*fraction;
        b[i].v+=dp/b[i].mass;
        b[i].omega+=(js[i].angular*fraction-cross(b[i].x,dp))/b[i].inertia;
    }
}
void oblique_history_and_budget(){
    Fixture s;const auto bs=s.b;auto reference_bodies=bs;auto reference_dem=s.dem;auto reference_nf=s.near;
    const double history0=s.dem.tangentialHistory(9,2);
    const auto initial=population_budget(s.f,s.b),grid0=population_budget(s.f,{});
    LBM predictor(s.f);predictor.collide_stream();
    const auto grid1=population_budget(predictor,{});
    // Independent boundary ledger: local collision conserves momentum, so
    // the raw grid angular change in the one unforced predictor is wrap flux.
    const auto boundary=grid1.l-grid0.l;
    const int count=5;const double h=1./count;
    const auto out=advance_hydro_contact_iterated(s.f,s.ib,s.dem,s.near,s.b,count,controls());
    const auto final=population_budget(s.f,s.b);
    double diss=0;
    for(int i=0;i<count;++i){
        replay_kick(reference_bodies,out.trial_impulse,.5*h);
        reference_nf.apply(reference_bodies,.5*h);diss+=reference_nf.stats.physical_dissipation;
        reference_dem.advance(reference_bodies,h,1);
        reference_nf.apply(reference_bodies,.5*h);diss+=reference_nf.stats.physical_dissipation;
        replay_kick(reference_bodies,out.trial_impulse,.5*h);
    }
    const double history=s.dem.tangentialHistory(9,2);
    const double he=std::abs(history-reference_dem.tangentialHistory(9,2));
    double xe=0,replay_e=0;
    for(std::size_t i=0;i<s.b.size();++i){
        xe=std::max({xe,norm(reference_bodies[i].x-s.b[i].x),std::abs(reference_bodies[i].angle-s.b[i].angle)});
        const auto& j=out.trial_impulse.at(i);const auto& jj=s.ib.hydrodynamic_impulse.at(i);
        const Vec2 dj=jj.linear-j.linear;
        const auto& p=reference_bodies[i];
        replay_e=std::max({replay_e,norm(p.v+dj/p.mass-s.b[i].v),
            std::abs(p.omega+(jj.angular-j.angular-cross(p.x,dj))/p.inertia-s.b[i].omega)});
    }
    const double pe=double(std::hypot(final.x-initial.x,final.y-initial.y));
    const double le=double(std::abs(final.l-initial.l-boundary));
    const double me=double(std::abs(final.m-initial.m));
    const double slip=marker_slip(s.f,s.ib,s.b);
    insist(out.outer_iterations>1&&out.particles.peak_contacts==1&&diss>1e-7,
           "expected active contact, near-field dissipation and multiple trials");
    insist(std::abs(history0)>1e-4&&std::abs(history-history0)>1e-3&&he<3e-12,
           "accepted history disagrees with a single trajectory from the old history");
    insist(xe<2e-12&&replay_e<2e-11&&std::abs(diss-out.particles.near_physical_dissipation)<2e-13,
           "trial geometry, hydrodynamic replacement or accepted dissipation was accumulated incorrectly");
    insist(pe<3e-10&&le<5e-9&&me<8e-10&&slip<2e-11,
           "population-based all-mobile physical budget or endpoint no slip failed");
    insist(std::abs(boundary)>1e-3&&std::abs(boundary-out.periodic_angular_flux)<1e-9,
           "periodic angular-flux ledger not independently recovered");
    for(std::size_t i=0;i<s.b.size();++i)insist(s.b[i].mass==bs[i].mass&&s.b[i].inertia==bs[i].inertia&&
            s.b[i].radius==bs[i].radius&&s.b[i].contact_offset==bs[i].contact_offset,"physical body parameters changed");
    insist(s.dem.kn==reference_dem.kn&&s.dem.kt==reference_dem.kt,"contact stiffness changed");
    std::cout<<"METRIC oblique_history_initial="<<history0<<" final="<<history<<" replay_error="<<he
        <<" position_angle_error="<<xe<<" replaced_velocity_error="<<replay_e<<" near_dissipation="<<diss
        <<" physical_p_error="<<pe<<" physical_l_error="<<le<<" mass_error="<<me
        <<" angular_wrap_flux="<<double(boundary)<<" marker_slip="<<slip<<" outer="<<out.outer_iterations<<'\n';
}

void exhaustion_rolls_back(){
    Fixture s;auto original=s;auto failure=controls();
    failure.max_iterations=1;failure.relative_tolerance=0.;failure.absolute_tolerance=1e-15;
    bool refused=false;
    try{(void)advance_hydro_contact_iterated(s.f,s.ib,s.dem,s.near,s.b,4,failure);}
    catch(const std::runtime_error&){refused=true;}
    insist(refused,"impossible one-iteration tolerance did not reject");
    insist(pop_error(s.f,original.f)==0&&s.f.rho==original.f.rho&&body_error(s.b,original.b)==0,
           "failed outer exchange changed fluid or particles");
    for(int i=0;i<s.f.n;++i)insist(norm(s.f.u[i]-original.f.u[i])==0,"failed outer exchange changed fluid macros");
    insist(s.dem.historySize()==original.dem.historySize()&&s.dem.tangentialHistory(9,2)==original.dem.tangentialHistory(9,2)
        &&s.dem.force_evaluations==original.dem.force_evaluations,"failed exchange committed contact or evaluation state");
    insist(s.near.stats.physical_dissipation==original.near.stats.physical_dissipation&&
        s.near.impulse.size()==original.near.impulse.size()&&s.near.pair_table.size()==original.near.pair_table.size()&&
        norm(s.near.impulse.at(0).linear-original.near.impulse.at(0).linear)==0,"failed exchange committed near-field state");
    for(std::size_t i=0;i<s.b.size();++i){
        insist(norm(s.ib.old_interior.at(i).p-original.ib.old_interior.at(i).p)==0&&
          s.ib.old_interior.at(i).angular==original.ib.old_interior.at(i).angular&&
          norm(s.ib.hydrodynamic_impulse.at(i).linear-original.ib.hydrodynamic_impulse.at(i).linear)==0&&
          s.ib.hydrodynamic_impulse.at(i).angular==original.ib.hydrodynamic_impulse.at(i).angular,
          "failed exchange committed IBM impulse/interior state");
    }
    // Repeat from the failed caller and its pristine pre-attempt copy. This
    // checks observable effects of private caches as well as public arrays.
    auto a=advance_hydro_contact_iterated(s.f,s.ib,s.dem,s.near,s.b,4,controls());
    auto z=advance_hydro_contact_iterated(original.f,original.ib,original.dem,original.near,original.b,4,controls());
    const double pe=pop_error(s.f,original.f),be=body_error(s.b,original.b);
    insist(pe<1e-15&&be<1e-15&&s.dem.tangentialHistory(9,2)==original.dem.tangentialHistory(9,2)&&
       a.outer_iterations==z.outer_iterations&&a.ibm_iterations==z.ibm_iterations,
       "retry after failed iteration disagrees with an untouched copy");
    std::cout<<"METRIC rollback_retry_population_error="<<pe<<" body_error="<<be
        <<" history="<<s.dem.tangentialHistory(9,2)<<" outer="<<a.outer_iterations<<'\n';
}
}
int main(){
    int failures=0;std::cout<<std::setprecision(12);
    auto run=[&](const char* name,auto test){
        try{test();std::cout<<"PASS "<<name<<'\n';}
        catch(const std::exception& e){++failures;std::cout<<"FAIL "<<name<<": "<<e.what()<<'\n';}
    };
    run("iterated_single_disk_prescribed_recoil_oracle",recoil_oracle);
    run("iterated_oblique_history_and_global_budget",oblique_history_and_budget);
    run("iterated_exhaustion_rollback_and_retry",exhaustion_rolls_back);
    return failures?1:0;
}
