// Synthetic plane-strain fixture: prescribed geometry, no fluid, biology or flexible rod.
#include "stepper.hpp"
#include <iomanip>
#include <iostream>
#include <string>
using namespace rhizo;
int main(int argc,char** argv){
 if(argc<3||argc>6)throw std::invalid_argument("growth_cell direct|cached steps [subdivisions=1] [advance_m=.0001] [symmetric|held]");
 std::string mode=argv[1],method=argc>5?argv[5]:"symmetric";int N=std::stoi(argv[2]),sub=argc>3?std::stoi(argv[3]):1;double travel=argc>4?std::stod(argv[4]):.00010;
 if((mode!="direct"&&mode!="cached")||N<2000||N%100!=0||sub<1||sub>32||!std::isfinite(travel)||travel<0||travel>.00010||(method!="symmetric"&&method!="held"))throw std::invalid_argument("invalid case");
 const double r=.00025,spacing=.000506,R=.00027,gap=.00002,end=.040,dt=end/N;
 std::vector<ibdem::Body> bodies;for(int j=-3;j<=3;++j)for(int i=0;i<8;++i){double x=spacing*(i+.5*(std::abs(j)%2)),y=spacing*std::sqrt(.75)*j;bool wall=std::abs(j)==3||i==7;bodies.push_back(ibdem::disk(int(bodies.size()),{x,y},r,2650,wall));}
 const auto initial=bodies;const double tip=-(R+r+gap),yc=.00008;
 std::vector<Edge> edges;for(int j=0;j<6*sub;++j)edges.push_back({j,j+1});std::vector<int> strand(edges.size(),0);
 auto geometry=[&](double time){
  double q=std::clamp(time/.03,0.,1.),d=travel*q*q*(3-2*q),rate=q<1?travel*6*q*(1-q)/.03:0;
  std::vector<Ball> nodes;std::vector<Motion> motion;
  for(int j=0;j<=6*sub;++j){double a=double(j)/sub,shape=std::max(0.,a-5.);
   nodes.push_back({{tip-(6-a)*.00035+shape*d,yc,0},R+.00001*(6-a)});
   motion.push_back({{shape*rate,0,0},0,0});}
  return std::make_pair(nodes,motion);
 };
 ibdem::DEM dem;dem.kn=2e5;dem.kt=4e4;dem.cn=.8;dem.ct=0;dem.mu=.35;
 PlanarLaw law(4e5,8e4,.8,.30);Search search(mode=="direct"?Mode::direct:Mode::cached,.00003,1e-13);DryRootStepper step;
 double work=0,power_error=0,peak=0,peak_time=0,bin_min=1e300,bin_max=-1e300;int iterations=0;
 std::cout<<"time_s,tip_advance_m,grain_root_reaction_N_per_m,max_grain_motion_m,root_contacts,grain_contacts,max_root_overlap_m,kinetic_J_per_m,stored_contact_J_per_m,root_actuation_work_J_per_m,kick_work_residual_J_per_m,kick_iterations,running_peak_force_N_per_m,peak_time_s,interval_min_force_N_per_m,interval_max_force_N_per_m\n"<<std::setprecision(16);
 for(int k=0;k<=N;++k){double t=k*dt;auto [nodes,nv]=geometry(t);auto g=grainGeometry(bodies);auto gv=grainMotion(bodies);auto hits=search.run(g,nodes,edges);
  auto loads=law.step(hits,g,gv,nodes,nv,edges,strand,method=="held"&&k<N?dt:0.);
  double reaction=0,overlap=0,maxmove=0,stored=law.tangentialEnergy()+dem.stats.elastic_energy;
  for(auto l:loads.node)reaction-=l.f.x;
  for(auto c:hits){overlap=std::max(overlap,-c.h.gap);if(c.h.gap<0)stored+=.5*law.kn*c.h.gap*c.h.gap;}
  for(size_t j=0;j<bodies.size();++j)maxmove=std::max(maxmove,ibdem::norm(bodies[j].x-initial[j].x));
  if(reaction>peak){peak=reaction;peak_time=t;}bin_min=std::min(bin_min,reaction);bin_max=std::max(bin_max,reaction);
  if(k%(N/100)==0){std::cout<<t<<','<<nodes.back().p.x-tip<<','<<reaction<<','<<maxmove<<','<<hits.size()<<','<<dem.stats.contact_count<<','<<overlap<<','<<kineticEnergy(bodies)<<','<<stored<<','<<work<<','<<power_error<<','<<iterations<<','<<peak<<','<<peak_time<<','<<bin_min<<','<<bin_max<<'\n';bin_min=1e300;bin_max=-1e300;}
  if(k==N)break;
  if(method=="symmetric"){
   auto [n1,v1]=geometry(t+dt);auto result=step.advance(bodies,dem,law,search,nodes,nv,n1,v1,edges,strand,t,dt);
   work+=result.root_work;power_error+=result.kick_power_residual;iterations+=result.kick_iterations;
  }else{
   for(size_t j=0;j<nodes.size();++j)work-=dt*dot(loads.node[j].f,nv[j].v);
   std::vector<ibdem::Vec2> f(g.size());std::vector<double> torque(g.size());for(size_t j=0;j<g.size();++j){f[j]={loads.grain[j].f.x,loads.grain[j].f.y};torque[j]=loads.grain[j].torque;}
   dem.advance(bodies,dt,1,f,torque);
  }
 }
}
