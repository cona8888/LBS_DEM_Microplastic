// Synthetic plane-strain contact fixture, NOT a prepared natural soil or living plant.
#include "traction.hpp"
#include "dem.hpp"
#include <iomanip>
#include <iostream>
#include <string>
using namespace rhizo;
int main(int argc,char** argv){if(argc!=3)throw std::invalid_argument("growth_cell direct|cached steps");std::string m=argv[1];int N=std::stoi(argv[2]);if((m!="direct"&&m!="cached")||N<2000||N%100!=0)throw std::invalid_argument("invalid case");
 const double r=.00025,spacing=.000506,R=.00027,gap=.00002,end=.040,travel=.00010,dt=end/N;
 std::vector<ibdem::Body> bodies;for(int j=-3;j<=3;++j)for(int i=0;i<8;++i){double x=spacing*(i+.5*(std::abs(j)%2));double y=spacing*std::sqrt(.75)*j;bool wall=std::abs(j)==3||i==7;bodies.push_back(ibdem::disk(int(bodies.size()),{x,y},r,2650,wall));}
 std::vector<ibdem::Body> initial=bodies;std::vector<Ball> nodes;std::vector<Edge> edges;double tip=-(R+r+gap),yc=.00008;
 for(int i=0;i<=6;++i){nodes.push_back({{tip-(6-i)*.00035,yc,0},R+.00001*(6-i)});if(i)edges.push_back({i-1,i});}std::vector<int> strand(6,0);
 ibdem::DEM dem;dem.kn=2e5;dem.kt=4e4;dem.cn=.8;dem.ct=0;dem.mu=.35;
 PlanarLaw law(4e5,8e4,.8,.30);Search search(m=="direct"?Mode::direct:Mode::cached,.00003,1e-13);
 std::cout<<"time_s,tip_advance_m,root_resistance_N_per_m,max_grain_motion_m,root_contacts,grain_contacts,max_root_overlap_m\n"<<std::setprecision(13);
 for(int k=0;k<=N;++k){double t=dt*k,q=std::min(t/.03,1.),d=travel*q*q*(3-2*q);nodes.back().p.x=tip+d;std::vector<Motion> nv(nodes.size());nv.back().v.x=q<1?travel*6*q*(1-q)/.03:0;
  std::vector<Ball> g;std::vector<Motion> gv;double maxmove=0;for(size_t i=0;i<bodies.size();++i){auto& b=bodies[i];g.push_back({{b.x.x,b.x.y,0},b.contactRadius()});gv.push_back({{b.v.x,b.v.y,0},b.omega,0});maxmove=std::max(maxmove,ibdem::norm(b.x-initial[i].x));}
  auto hits=search.run(g,nodes,edges);auto loads=law.step(hits,g,gv,nodes,nv,edges,strand,k==N?0:dt);double reaction=0,overlap=0;for(auto v:loads.node)reaction-=v.f.x;for(auto c:hits)overlap=std::max(overlap,-c.h.gap);
  if(k%(N/100)==0)std::cout<<t<<','<<d<<','<<reaction<<','<<maxmove<<','<<hits.size()<<','<<dem.stats.contact_count<<','<<overlap<<'\n';
  if(k==N)break;
  std::vector<ibdem::Vec2> ext(g.size());std::vector<double> tor(g.size());for(size_t i=0;i<g.size();++i){ext[i]={loads.grain[i].f.x,loads.grain[i].f.y};tor[i]=loads.grain[i].torque;}
  dem.advance(bodies,dt,1,ext,tor);
 }}
