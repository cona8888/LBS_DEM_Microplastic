#include "ibm.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using ibdem::Body;
using ibdem::IBM;
using ibdem::LBM;
using ibdem::Vec2;

void check(bool ok,const std::string& message) {
    if(!ok) throw std::runtime_error(message);
}

// Recover momentum directly from populations, independently of the cached
// macroscopic arrays and the IBM interior_momentum implementation.
Vec2 cell_momentum(const LBM& f,int cell) {
    Vec2 p;
    for(int q=0;q<LBM::q_count;++q) {
        const double value=f.f[static_cast<std::size_t>(q)*f.n+cell];
        p.x+=LBM::cx[q]*value;
        p.y+=LBM::cy[q]*value;
    }
    return p;
}

struct PhysicalMomentum { long double x=0,y=0,angular=0; };

PhysicalMomentum physical_momentum(const LBM& f,const std::vector<Body>& bodies) {
    PhysicalMomentum total;
    // Only the fluid outside the disks is physical. The IBM fluid retained
    // inside each disk must be excluded before adding physical solid inertia.
    for(int y=0;y<f.ny;++y) for(int x=0;x<f.nx;++x) {
        double exterior=1.0;
        Vec2 first{double(x),double(y)};
        for(const Body& body:bodies){auto q=ibdem::disk_cell_moments(body.x,body.radius,x,y);exterior-=q.area;first-=q.first;}
        const Vec2 momentum=cell_momentum(f,y*f.nx+x);
        const Vec2 p=momentum*exterior;
        total.x+=p.x;
        total.y+=p.y;
        total.angular+=static_cast<long double>(first.x)*momentum.y-static_cast<long double>(first.y)*momentum.x;
    }
    for(const Body& body:bodies) {
        const Vec2 p=body.v*body.mass;
        total.x+=p.x;
        total.y+=p.y;
        total.angular+=static_cast<long double>(body.x.x)*p.y-
                       static_cast<long double>(body.x.y)*p.x+
                       body.inertia*body.omega;
    }
    return total;
}

std::vector<Body> free_disks() {
    std::vector<Body> b{
        ibdem::disk(1,{24.3,21.2},4.2,0.70),
        ibdem::disk(2,{34.4,21.7},3.8,1.40)
    };
    b[0].v={0.012,-0.006};b[0].omega=0.0008;
    b[1].v={-0.008,0.003};b[1].omega=-0.0006;
    return b;
}

void initialize_flow(LBM& f,bool variable_density=false) {
    std::vector<Vec2> u(f.n);
    for(int y=0;y<f.ny;++y) for(int x=0;x<f.nx;++x) {
        const int i=y*f.nx+x;
        u[i]={0.009+0.001*std::sin(2*ibdem::pi*y/f.ny),
              0.002*std::cos(2*ibdem::pi*x/f.nx)};
    }
    f.initialize(u);
    if(variable_density) {
        for(int y=0;y<f.ny;++y) for(int x=0;x<f.nx;++x) {
            const int i=y*f.nx+x;
            const double density=1.0+0.01*std::sin(2*ibdem::pi*x/f.nx)*
                                           std::cos(2*ibdem::pi*y/f.ny);
            const auto eq=LBM::equilibrium(density,u[i]);
            for(int q=0;q<LBM::q_count;++q) f.f[static_cast<std::size_t>(q)*f.n+i]=eq[q];
        }
        f.macros();
    }
}

void test_operator_entries_and_cross_body_terms() {
    LBM f(64,48);initialize_flow(f,true);
    auto bodies=free_disks();IBM ibm;ibm.initialize(f,bodies);
    const int dim=2*static_cast<int>(ibm.markers.size());
    std::vector<double> unit(dim,0.0);
    double entry_error=0,compact_error=0,cross_body=0;
    for(int col=0;col<dim;++col) {
        unit[col]=1.0;
        const auto compact=ibm.apply_operator(f,bodies,unit,true);
        const auto full=ibm.apply_operator(f,bodies,unit,false);
        unit[col]=0.0;
        for(int row=0;row<dim;++row) {
            entry_error=std::max(entry_error,std::abs(compact[row]-ibm.operator_entry(f,bodies,row,col)));
            compact_error=std::max(compact_error,std::abs(compact[row]-full[row]));
            if(ibm.markers[row/2].body!=ibm.markers[col/2].body)
                cross_body=std::max(cross_body,std::abs(compact[row]));
        }
    }
    check(entry_error<2e-13,"IBM assembled entries disagree with the matrix-free operator");
    check(compact_error<2e-13,"IBM compact/full-grid operators disagree");
    check(cross_body>1e-6,"Operator test failed to exercise nonzero cross-body coupling");
    std::cout<<"  independent operator max errors: entry="<<entry_error
             <<" compact="<<compact_error<<" cross-body="<<cross_body<<'\n';
}

void test_transient_physical_momentum() {
    LBM f(64,48);initialize_flow(f);
    auto bodies=free_disks();IBM ibm;
    ibm.relative_tolerance=1e-11;ibm.initialize(f,bodies);
    const auto initial=physical_momentum(f,bodies);
    // This instantaneous coupling has no periodic streaming angular flux.
    ibm.couple(f,bodies);
    auto after=physical_momentum(f,bodies);
    check(std::hypot(double(after.x-initial.x),double(after.y-initial.y))<3e-10,
          "Instantaneous physical linear momentum is not conserved");
    check(std::abs(double(after.angular-initial.angular))<3e-8,
          "Instantaneous physical angular momentum is not conserved");
    double max_drift=0;
    for(int step=0;step<12;++step) {
        f.collide_stream();
        for(Body& body:bodies) {body.x+=body.v;body.angle+=body.omega;}
        ibm.couple(f,bodies);
        after=physical_momentum(f,bodies);
        max_drift=std::max(max_drift,std::hypot(double(after.x-initial.x),double(after.y-initial.y)));
        check(ibm.stats.max_slip<3e-10,"Transient IBM no-slip residual is too large");
    }
    // Angular momentum is not asserted across periodic streaming: periodic
    // boundary flux can carry angular momentum about the chosen origin.
    check(max_drift<3e-9,"Moving-interior physical momentum drifts across predictor/coupling steps");
    std::cout<<"  independent transient physical momentum drift="<<max_drift<<'\n';
}

void test_fixed_disk_manufactured_impulse() {
    LBM f(48,40);
    std::vector<Body> bodies{ibdem::disk(7,{23.35,19.6},4.4,1.0,true)};
    IBM ibm;ibm.relative_tolerance=1e-11;ibm.build_geometry(f,bodies);
    std::vector<Vec2> spread(f.n);
    Vec2 expected;
    for(std::size_t m=0;m<ibm.markers.size();++m) {
        const Vec2 lambda{0.0004+0.0002*std::sin(0.7*m),-0.0003+0.0001*std::cos(0.5*m)};
        expected+=lambda;
        for(int z=0;z<16;++z) spread[ibm.markers[m].node[z]]+=lambda*ibm.markers[m].w[z];
    }
    std::vector<Vec2> u(f.n);
    for(int i=0;i<f.n;++i)u[i]=-spread[i];
    f.initialize(u);ibm.initialize(f,bodies);
    Vec2 before;
    for(int i=0;i<f.n;++i)before+=cell_momentum(f,i);
    ibm.couple(f,bodies);
    Vec2 after;double velocity_error=0;
    for(int i=0;i<f.n;++i) {
        after+=cell_momentum(f,i);
        velocity_error=std::max(velocity_error,ibdem::norm(f.u[i]));
    }
    check(ibdem::norm(after-before-expected)<3e-12,"Manufactured fixed-disk impulse was not recovered");
    check(velocity_error<3e-11,"Manufactured fixed-disk flow was not cancelled");
    check(ibdem::norm(bodies[0].v)==0.0 && bodies[0].omega==0.0,"Fixed disk moved");
}

void test_preconditioner_equivalence_in_motion() {
    LBM a(64,48),b(64,48);initialize_flow(a);initialize_flow(b);
    auto ba=free_disks(),bb=ba;
    IBM ref(IBM::Mode::Reference),fast(IBM::Mode::CachedBlocks);
    ref.relative_tolerance=1e-11;fast.relative_tolerance=1e-11;
    ref.initialize(a,ba);fast.initialize(b,bb);
    bool reused=false;int ref_iterations=0,fast_iterations=0;
    for(int step=0;step<10;++step) {
        a.collide_stream();b.collide_stream();
        for(Body& body:ba){body.x+=body.v;body.angle+=body.omega;}
        for(Body& body:bb){body.x+=body.v;body.angle+=body.omega;}
        ref.couple(a,ba);fast.couple(b,bb);
        reused|=!fast.stats.preconditioner_rebuilt;
        ref_iterations+=ref.stats.iterations;fast_iterations+=fast.stats.iterations;
    }
    double error=0;
    for(std::size_t i=0;i<a.f.size();++i)error=std::max(error,std::abs(a.f[i]-b.f[i]));
    for(std::size_t k=0;k<ba.size();++k) {
        error=std::max(error,ibdem::norm(ba[k].x-bb[k].x));
        error=std::max(error,ibdem::norm(ba[k].v-bb[k].v));
        error=std::max(error,std::abs(ba[k].omega-bb[k].omega));
    }
    check(reused,"Matched-physics test never exercised a reused block preconditioner");
    check(error<5e-9,"Jacobi and cached-block GMRES alter the matched coupled solution");
    std::cout<<"  independent matched-physics max difference="<<error
             <<" iterations Jacobi="<<ref_iterations<<" blocks="<<fast_iterations<<'\n';
}
} // namespace

int run_ibm_independent_tests() {
    struct Test {const char* name;void(*run)();};
    const Test tests[]{
        {"IBM independent operator columns and cross-body terms",test_operator_entries_and_cross_body_terms},
        {"IBM independent transient physical momentum",test_transient_physical_momentum},
        {"IBM manufactured fixed-disk impulse",test_fixed_disk_manufactured_impulse},
        {"IBM matched-physics moving preconditioners",test_preconditioner_equivalence_in_motion}
    };
    int failed=0;
    for(const auto& test:tests)try {
        test.run();std::cout<<"PASS "<<test.name<<'\n';
    }catch(const std::exception& e) {
        ++failed;std::cerr<<"FAIL "<<test.name<<": "<<e.what()<<'\n';
    }
    return failed;
}

#ifdef IBDEM_IBM_INDEPENDENT_TEST_MAIN
int main(){return run_ibm_independent_tests();}
#endif
