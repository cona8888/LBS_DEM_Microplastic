// A native equilibrium probe using the unmodified parent ibdem::DEM stepper.
// Damping is only a relaxation device; pseudo-time is not hydraulic time.
#include "dem.hpp"
#include <algorithm>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace ibdem;
int main(int argc,char** argv){
 try {
    if(argc!=5) throw std::invalid_argument("usage: probe gap_m support_gap_m field_force_N_per_m stiffness_N_per_m2");
    auto arg=[&](int j){std::string s=argv[j]; size_t n=0; double v=std::stod(s,&n); if(n!=s.size()||!std::isfinite(v))throw std::invalid_argument("Invalid number"); return v;};
    const double g=arg(1), support=arg(2), field=arg(3), k=arg(4), R=.001, r=.00035;
    if(g<=0||support<=0||k<=0)throw std::invalid_argument("Nonpositive geometry or stiffness");
    std::vector<Body> b={disk(0,{0,0},R,1100,true),disk(1,{R+r+g,0},r,2650)};
    DEM dem; dem.kn=1e7;dem.kt=3e6;dem.mu=.45;
    double gap=g, v=0; const double damp=2*std::sqrt(k*b[1].mass), dt=.06*std::sqrt(b[1].mass/k);
    for(int j=0;j<2000;++j){
       double res=field+k*(support-gap);
       if(std::abs(res)<2e-10 && std::abs(v)<1e-8){std::cout<<std::setprecision(17)<<gap<<' '<<res<<' '<<j<<'\n'; return 0;}
       dem.advance(b,dt,1,{{-field,0},{res-damp*v,0}});
       gap=b[1].x.x-R-r;v=b[1].v.x;
       if(gap<=0||dem.stats.contact_count)throw std::runtime_error("Open-pore benchmark cannot enter contact");
    }
    throw std::runtime_error("Native grain did not equilibrate");
 }catch(const std::exception &e){std::cerr<<e.what()<<'\n';return 2;}
}
