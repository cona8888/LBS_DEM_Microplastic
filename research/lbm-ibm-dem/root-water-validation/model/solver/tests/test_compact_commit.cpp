#include "ibm.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>
using namespace ibdem;
void require(bool v,const char* m){if(!v)throw std::runtime_error(m);}
double fielddiff(const LBM& a,const LBM& b){
    double e=0;for(size_t i=0;i<a.f.size();++i)e=std::max(e,std::abs(a.f[i]-b.f[i]));
    for(int i=0;i<a.n;++i){e=std::max(e,norm(a.u[i]-b.u[i]));e=std::max(e,std::abs(a.rho[i]-b.rho[i]));}
    return e;
}
int main(){try{
    LBM a(34,28);std::vector<Vec2> v(a.n);
    for(int i=0;i<a.n;++i)v[i]={.008*std::sin(.03*i),.013*std::cos(.05*i)};
    a.initialize(v);a.collide_stream();LBM b=a;
    std::vector<int> nodes;std::vector<Vec2> q,dense(a.n);
    for(int i=1;i<a.n;i+=17){nodes.push_back(i);q.push_back({.0002*std::sin(i),-.0003*std::cos(i)});dense[i]=q.back();}
    a.apply_impulse(dense);b.apply_indexed_impulse(nodes,q);
    double err=fielddiff(a,b);require(err<3e-15,"Indexed/full population kicks disagree");
    std::cout<<"PASS compact_full_d2q9_population_and_macroscopic_state max_abs="<<err<<"\n";
    const LBM pre=b;int failed=0;
    for(int test=0;test<4;++test){auto nd=nodes;auto g=q;
        if(test==0)nd[2]=nd[1];
        if(test==1)nd.back()=a.n;
        if(test==2)g.back().x=std::numeric_limits<double>::quiet_NaN();
        if(test==3)g.pop_back();
        try{b.apply_indexed_impulse(nd,g);}catch(const std::invalid_argument&){++failed;}
    }
    require(failed==4&&fielddiff(pre,b)==0,"Invalid indexed input not atomic");
    std::cout<<"PASS compact_input_prevalidation_and_rollback rejected="<<failed<<"\n";
    LBM f(48,36),g=f;std::vector<Body> p={disk(0,{19.2,17.1},3.5,1.2),disk(1,{27.1,17.3},3.5,1.35)};
    p[0].v={.001,.002};p[1].v={-.002,0};p[1].omega=.0005;auto r=p;
    IBM i(IBM::Mode::CachedBlocks),j(IBM::Mode::CachedBlocks);i.marker_retraction=j.marker_retraction=.3;
    j.compact_commit=true;i.initialize(f,p);j.initialize(g,r);double maxall=0;
    for(int k=0;k<24;++k){
        for(auto& d:p){d.x+=d.v;d.angle+=d.omega;}for(auto& d:r){d.x+=d.v;d.angle+=d.omega;}
        f.collide_stream();g.collide_stream();i.couple(f,p);j.couple(g,r);
        maxall=std::max(maxall,fielddiff(f,g));
        for(size_t m=0;m<p.size();++m){maxall=std::max({maxall,norm(p[m].x-r[m].x),norm(p[m].v-r[m].v),std::abs(p[m].omega-r[m].omega),std::abs(p[m].angle-r[m].angle),norm(i.hydrodynamic_impulse[m].linear-j.hydrodynamic_impulse[m].linear),std::abs(i.hydrodynamic_impulse[m].angular-j.hydrodynamic_impulse[m].angular)});}
    }
    require(maxall<1e-10,"Dense/active coupled trajectories disagree");
    std::cout<<"PASS compact_two_way_repeated_moving_disks max_abs="<<maxall<<"\nTOTAL_FAILURES 0\n";return 0;
}catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
