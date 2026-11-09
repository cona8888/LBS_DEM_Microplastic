#include "ibm.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

namespace {
using namespace ibdem;

void require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
template<class Function> void check(const char* name,Function fn,int& failures){
    try{fn();std::cout<<"PASS "<<name<<'\n';}
    catch(const std::exception& e){++failures;std::cout<<"FAIL "<<name<<": "<<e.what()<<'\n';}
}

struct Momentum {Vec2 linear;double angular=0.0;};

// Recover physical exterior-fluid momentum directly from populations, using
// full-grid geometric integration rather than IBM's cached active-node lists.
Momentum exterior_momentum(const LBM& f,const std::vector<Body>& bodies){
    long double px=0,py=0,angular=0;
    for(int y=0;y<f.ny;++y)for(int x=0;x<f.nx;++x){
        Vec2 j;
        const int cell=y*f.nx+x;
        for(int q=0;q<LBM::q_count;++q){const double population=f.f[std::size_t(q)*f.n+cell];j.x+=LBM::cx[q]*population;j.y+=LBM::cy[q]*population;}
        double exterior=1.0;Vec2 first{double(x),double(y)};
        for(const auto& body:bodies){auto m=disk_cell_moments(body.x,body.radius,x,y);exterior-=m.area;first-=m.first;}
        px+=static_cast<long double>(exterior)*j.x;py+=static_cast<long double>(exterior)*j.y;
        angular+=static_cast<long double>(first.x)*j.y-static_cast<long double>(first.y)*j.x;
    }
    return {{double(px),double(py)},double(angular)};
}

double state_difference(const LBM& f,const LBM& g,const std::vector<Body>& b,const std::vector<Body>& c){
    double error=0;
    for(std::size_t i=0;i<f.f.size();++i)error=std::max(error,std::abs(f.f[i]-g.f[i]));
    for(std::size_t i=0;i<b.size();++i)error=std::max({error,norm(b[i].x-c[i].x),norm(b[i].v-c[i].v),std::abs(b[i].angle-c[i].angle),std::abs(b[i].omega-c[i].omega)});
    return error;
}

void require_unchanged(const std::vector<Body>& bodies,const std::vector<Body>& initial){
    for(std::size_t i=0;i<bodies.size();++i){const auto& a=bodies[i];const auto& b=initial[i];
        require(a.x.x==b.x.x&&a.x.y==b.x.y&&a.v.x==b.v.x&&a.v.y==b.v.y&&a.angle==b.angle&&a.omega==b.omega&&a.mass==b.mass&&a.inertia==b.inertia&&a.radius==b.radius&&a.fixed==b.fixed,"Prescribed coupling changed a physical body state");
    }
}
}

int test_ibm_prescribed(){
    using namespace ibdem;
    int failures=0;
    check("ibm_prescribed_uniform_translation",[]{
        LBM f(64,48);const Vec2 velocity{.007,-.003};f.initialize(velocity);
        std::vector<Body>b{disk(0,{22.3,22.7},5.1,.8,true),disk(1,{37.6,22.9},4.5,2.5)};
        for(auto& p:b)p.v=velocity;
        const auto initial=b;IBM ib;ib.relative_tolerance=1e-12;ib.initialize(f,b);
        for(int step=0;step<12;++step){f.collide_stream();ib.couple_prescribed(f,b);}
        require_unchanged(b,initial);
        require(ib.stats.max_slip<2e-12,"Prescribed uniform velocity was not imposed");
        for(auto u:f.u)require(norm(u-velocity)<2e-12,"Comoving fluid acquired a spurious disturbance");
        for(const auto& h:ib.hydrodynamic_impulse)require(norm(h.linear)<2e-11&&std::abs(h.angular)<2e-9,"Comoving disk acquired a spurious reaction");
    },failures);

    check("ibm_prescribed_reaction_and_global_torque_budget",[]{
        LBM f(64,48);f.initialize({.003,-.002});
        std::vector<Body>b{disk(0,{22.3,23.7},5.0,.8,true),disk(1,{35.8,24.2},5.0,2.5)};
        b[0].v={.011,.004};b[0].omega=.0008;b[1].v={-.006,.002};b[1].omega=-.0004;
        const auto initial=b;IBM ib;ib.relative_tolerance=1e-12;ib.initialize(f,b);
        const auto before=exterior_momentum(f,b);ib.couple_prescribed(f,b);const auto after=exterior_momentum(f,b);
        require_unchanged(b,initial);require(ib.hydrodynamic_impulse.size()==b.size(),"Missing per-body prescribed reactions");
        Vec2 reaction;double torque=0;for(const auto& h:ib.hydrodynamic_impulse){reaction+=h.linear;torque+=h.angular;}
        const double pe=norm(after.linear-before.linear+reaction),le=std::abs(after.angular-before.angular+torque);
        require(pe<3e-11&&le<3e-9,"Prescribed reaction does not balance physical fluid momentum");
        require(norm(ib.hydrodynamic_impulse[0].linear)>1e-4&&std::abs(ib.hydrodynamic_impulse[0].angular)>1e-3,"Prescribed fixed body did not receive the required reaction");
        require(ib.stats.max_slip<2e-11,"Prescribed rotation/translation has excessive slip");
        std::cout<<"METRIC prescribed_linear_budget_error="<<pe<<" prescribed_global_angular_budget_error="<<le<<'\n';
    },failures);

    check("ibm_dynamic_and_fixed_support_impulse_budget",[]{
        LBM f(64,48);f.initialize({.006,-.001});
        std::vector<Body>b{disk(0,{22.3,23.7},5.0,.8),disk(1,{35.8,24.2},5.0,2.5,true)};
        b[0].v={.013,-.004};b[0].omega=.0006;const auto initial=b;
        IBM ib;ib.relative_tolerance=1e-12;ib.initialize(f,b);const auto before=exterior_momentum(f,b);ib.couple(f,b);const auto after=exterior_momentum(f,b);
        const Vec2 dp=(b[0].v-initial[0].v)*b[0].mass;
        const double dl=cross(b[0].x,dp)+b[0].inertia*(b[0].omega-initial[0].omega);
        require(norm(dp-ib.hydrodynamic_impulse[0].linear)<2e-14,"Mobile body momentum disagrees with exposed hydrodynamic impulse");
        require(std::abs(dl-ib.hydrodynamic_impulse[0].angular)<2e-12,"Mobile body angular momentum disagrees with exposed global impulse");
        require(norm(after.linear-before.linear+dp+ib.hydrodynamic_impulse[1].linear)<3e-11,"Fixed support omitted from physical linear budget");
        require(std::abs(after.angular-before.angular+dl+ib.hydrodynamic_impulse[1].angular)<3e-9,"Fixed support omitted from physical angular budget");
        require(norm(ib.hydrodynamic_impulse[1].linear)>1e-4,"Fixed hydrodynamic reaction was not recorded");
    },failures);

    check("ibm_prescribed_dynamic_cache_switch_matches_fresh",[]{
        LBM f(64,48);f.initialize({.002,-.001});
        std::vector<Body>b{disk(0,{22.3,23.7},5.0,.8),disk(1,{34.3,24.2},5.0,2.5,true)};
        b[0].v={.009,-.002};b[0].omega=.0003;b[1].v={-.003,.001};b[1].omega=-.0002;
        IBM switched;switched.relative_tolerance=1e-12;switched.initialize(f,b);switched.couple_prescribed(f,b);
        LBM control=f;auto c=b;IBM fresh;fresh.relative_tolerance=1e-12;fresh.initialize(control,c);
        f.collide_stream();control.collide_stream();switched.couple(f,b);fresh.couple(control,c);
        require(switched.stats.preconditioner_rebuilt,"Prescribed-to-dynamic switch reused constrained factors");
        double error=state_difference(f,control,b,c);require(error<3e-11,"Prescribed-to-dynamic switch changed the dynamic solution");
        LBM prescribed_control=f;c=b;fresh.initialize(prescribed_control,c);
        f.collide_stream();prescribed_control.collide_stream();switched.couple_prescribed(f,b);fresh.couple_prescribed(prescribed_control,c);
        require(switched.stats.preconditioner_rebuilt,"Dynamic-to-prescribed switch reused physical-mass factors");
        error=std::max(error,state_difference(f,prescribed_control,b,c));require(error<3e-11,"Dynamic-to-prescribed switch changed the constraint solution");
        std::cout<<"METRIC prescribed_dynamic_switch_max_difference="<<error<<'\n';
    },failures);

    check("ibm_regular_fixed_body_ignores_stored_velocity",[]{
        LBM f(48,40);std::vector<Body>b{disk(0,{23.3,20.7},5.0,1.2,true)};
        b[0].v={.07,-.02};b[0].omega=.01;const auto initial=b;const auto populations=f.f;
        IBM ib;ib.initialize(f,b);ib.couple(f,b);require_unchanged(b,initial);
        require(f.f==populations,"Regular fixed-body coupling imposed a nonzero stored velocity");
        require(ib.stats.max_slip<1e-14&&norm(ib.hydrodynamic_impulse[0].linear)<1e-14&&std::abs(ib.hydrodynamic_impulse[0].angular)<1e-13,"Regular fixed body generated a spurious impulse at rest");
    },failures);

    check("ibm_retracted_markers_current_operator_physical_budget_and_guards",[]{
        LBM f(64,48);f.initialize({.004,-.002});
        std::vector<Body>b{disk(0,{22.3,23.7},5.0,.8,true),disk(1,{34.3,24.2},5.0,2.5)};
        b[0].v={.008,.003};b[0].omega=.0006;b[1].v={-.004,.001};b[1].omega=-.0003;
        const auto initial=b;IBM ib;require(ib.marker_retraction==0.0,"Marker retraction changed the default method");
        ib.relative_tolerance=1e-12;ib.initialize(f,b);ib.couple_prescribed(f,b);
        const auto marker_count=ib.markers.size();const auto interior_before=ib.interior_momentum(f,b);
        const auto before=exterior_momentum(f,b);
        ib.marker_retraction=.3;ib.build_geometry(f,b);
        const auto interior_after=ib.interior_momentum(f,b);
        require(ib.markers.size()==marker_count,"Retraction changed the physical-circumference marker count");
        for(std::size_t i=0;i<b.size();++i){
            require(norm(interior_after[i].p-interior_before[i].p)<1e-15&&std::abs(interior_after[i].angular-interior_before[i].angular)<1e-13,"Retraction changed the physical fictitious-interior integration");
        }
        for(const auto& marker:ib.markers){
            require(std::abs(norm(marker.r)-(b[marker.body].radius-.3))<2e-14,"Retraction did not use the actual numerical marker arm");
            double sum=0;Vec2 first;
            for(int k=0;k<16;++k){sum+=marker.w[k];first+=Vec2{double(marker.node[k]%f.nx),double(marker.node[k]/f.nx)}*marker.w[k];}
            require(std::abs(sum-1)<2e-14&&norm(first-marker.x)<2e-13,"Retracted spreading kernel lost its zeroth/first moments");
        }
        const int n=2*ib.markers.size();std::vector<double>x(n);
        for(int i=0;i<n;++i)x[i]=std::sin(.37*i+.2);
        const auto compact=ib.apply_operator(f,b,x,true),full=ib.apply_operator(f,b,x,false);
        double operator_error=0;
        for(int i=0;i<n;++i){double assembled=0;for(int j=0;j<n;++j)assembled+=ib.operator_entry(f,b,i,j)*x[j];
            operator_error=std::max({operator_error,std::abs(compact[i]-full[i]),std::abs(compact[i]-assembled)});
        }
        require(operator_error<3e-14,"Retracted current operator implementations disagree");
        ib.couple_prescribed(f,b);require(ib.stats.preconditioner_rebuilt,"Changed retraction did not rebuild cached factors");
        require_unchanged(b,initial);const auto after=exterior_momentum(f,b);
        Vec2 reaction;double torque=0;for(const auto& h:ib.hydrodynamic_impulse){reaction+=h.linear;torque+=h.angular;}
        const double pe=norm(after.linear-before.linear+reaction),le=std::abs(after.angular-before.angular+torque);
        require(pe<3e-11&&le<3e-9,"Retracted IBM violated the physical exterior-fluid reaction budget");
        require(ib.stats.max_slip<2e-11,"Retracted prescribed constraints did not converge");
        for(double bad:{-.1,5.0,6.0,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){
            ib.marker_retraction=bad;bool rejected=false;
            try{ib.build_geometry(f,b);}catch(const std::invalid_argument&){rejected=true;}
            require(rejected,"Invalid numerical marker retraction was accepted");
        }
        std::cout<<"METRIC retracted_operator_error="<<operator_error<<" retracted_linear_budget_error="<<pe<<" retracted_angular_budget_error="<<le<<'\n';
    },failures);
    return failures;
}

#ifdef IBDEM_IBM_PRESCRIBED_TEST_MAIN
int main(){return test_ibm_prescribed()?1:0;}
#endif
