// Manufactured dry root-contact test; SI, 2D per unit depth. Uses parent ibdem::DEM.
#include "traction.hpp"
#include "dem.hpp"
#include <iomanip>
#include <iostream>
#include <string>
using namespace rhizo;
int main(int argc,char** argv){if(argc!=4){std::cerr<<"usage: native_probe tip|radial direct|cached steps\n";return 2;}
 std::string path=argv[1],mode=argv[2];int N=std::stoi(argv[3]);if((path!="tip"&&path!="radial")||(mode!="direct"&&mode!="cached")||N<2000)throw std::invalid_argument("invalid test parameters");
 double r=.00035,R=.00035,gap=.00001,advance=.00002,kn=1e5,ks=1e3,ramp=.03,end=.06,dt=end/N;bool axial=path=="tip";V axis=axial?V{1,0,0}:V{0,1,0};V initial=axial?V{R+r+gap,0,0}:V{-.0005,R+r+gap,0};
 std::vector<ibdem::Body> bodies={ibdem::disk(1,{initial.x,initial.y},r,2650)};ibdem::DEM dem;Search search(mode=="direct"?Mode::direct:Mode::cached,.000005,1e-14);PlanarLaw law(kn,0,0,0);double damp=2*std::sqrt((kn+ks)*bodies[0].mass),target=kn*ks/(kn+ks)*(advance-gap);
 std::cout<<"time_s,imposed_advance_m,grain_m,reaction_N_per_m,overlap_m\n"<<std::setprecision(14);
 for(int k=0;k<=N;++k){double t=k*dt,d=advance*std::min(1.,t/ramp);std::vector<Ball> n={{{-.001,0,0},R},{{0,0,0},R}};if(axial)n[1].p.x+=d;else for(auto& x:n)x.r+=d;
 auto& b=bodies[0];std::vector<Ball> g={{{b.x.x,b.x.y,0},b.contactRadius()}};auto hits=search.run(g,n,{{0,1}});std::vector<Motion> nv(2);if(k*dt<ramp){if(axial)nv[1].v.x=advance/ramp;else for(auto& z:nv)z.rdot=advance/ramp;}auto loads=law.step(hits,g,{{{b.v.x,b.v.y,0},b.omega,0}},n,nv,{{0,1}},{0},dt);double reaction=dot(loads.grain[0].f,axis),x=dot(g[0].p-initial,axis);
 if(k%std::max(1,N/150)==0||k==N)std::cout<<t<<','<<d<<','<<x<<','<<reaction<<','<<(hits.empty()?0:std::max(0.,-hits.front().h.gap))<<'\n';
 if(k==N){if(std::abs(reaction-target)>target*1e-5)throw std::runtime_error("static series spring benchmark failed");break;}
 double total=reaction-ks*x-damp*dot({b.v.x,b.v.y,0},axis);dem.advance(bodies,dt,1,{{total*axis.x,total*axis.y}});
 }}
