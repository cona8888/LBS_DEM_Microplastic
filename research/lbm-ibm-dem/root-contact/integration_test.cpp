#include "stepper.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
using namespace rhizo;
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
struct Metric{double energy=0,position=0,final_state=0,power=0;};
Metric oscillator(int per,bool corrected,double zeta,std::ostream* series=nullptr){
 const double r=.00025,R=.00027,kn=4e5,delta=2e-6,A=1e-8,equilibrium=R+r-delta;
 auto initial=ibdem::disk(7,{0,equilibrium+A},r,2650);std::vector<ibdem::Body> b={initial};
 ibdem::DEM dem;Search search(Mode::cached,3e-5,1e-13);PlanarLaw law(kn,0,2*zeta*std::sqrt(kn*initial.mass),0);DryRootStepper step;
 std::vector<Ball> n={{{-.001,0,0},R},{{.001,0,0},R}};std::vector<Motion> w(2);std::vector<Edge> e={{0,1}};
 const double omega=std::sqrt(kn/initial.mass),dt=2*ibdem::pi/(omega*per),E0=.5*kn*A*A;
 const int cycles=zeta==0?20:5;Metric result;
 const SupportLaw preload=[&](const auto&,double){return std::vector<Load>{{{0,-kn*delta,0},0}};};
 for(int j=0;j<=cycles*per;++j){double t=j*dt,x=b[0].x.y-equilibrium,v=b[0].v.y;
  double wd=omega*std::sqrt(1-zeta*zeta),decay=std::exp(-zeta*omega*t);
  double exact=A*decay*(std::cos(wd*t)+zeta*omega/wd*std::sin(wd*t));
  double exactv=-A*decay*omega*omega/wd*std::sin(wd*t);
  double energy=.5*initial.mass*v*v+.5*kn*x*x;
  result.energy=std::max(result.energy,std::abs(energy/E0-1));
  result.position=std::max(result.position,std::abs(x-exact)/A);
  if(series&&j%std::max(1,per/50)==0)*series<<(corrected?"symmetric":"held")<<','<<per<<','<<zeta<<','<<std::setprecision(16)<<t<<','<<x<<','<<exact<<','<<energy/E0<<'\n';
  if(j==cycles*per){result.final_state=std::hypot((x-exact)/A,(v-exactv)/(A*omega));break;}
  if(corrected){auto s=step.advance(b,dem,law,search,n,w,n,w,e,{0},t,dt,preload);result.power=std::max(result.power,s.kick_power_residual/E0);}
  else{auto l=law.step(search.run(grainGeometry(b),n,e),grainGeometry(b),grainMotion(b),n,w,e,{0},dt);
   dem.advance(b,dt,1,{{l.grain[0].f.x,l.grain[0].f.y-kn*delta}});}
 }
 return result;
}
void tangential_oscillator(){
 const double r=.00025,R=.00027,delta=2e-6,kn=4e5,kt=8e4,A=1e-8;
 std::vector<ibdem::Body> b={ibdem::disk(7,{0,R+r-delta},r,2650)};ibdem::DEM dem;
 std::vector<Ball> n={{{-.001,0,0},R},{{.001,0,0},R}};std::vector<Motion> w(2);std::vector<Edge> e={{0,1}};
 Search search(Mode::cached,3e-5,1e-13);PlanarLaw law(kn,kt,0,.5);DryRootStepper step;
 auto hits=search.run(grainGeometry(b),n,e);auto seed=grainMotion(b);seed[0].v.x=-1;
 law.step(hits,grainGeometry(b),seed,n,w,e,{0},A);
 const double mass=b[0].mass,inertia=b[0].inertia,lever=r-delta/2;
 const double omega=std::sqrt(kt*(1/mass+lever*lever/inertia)),dt=2*ibdem::pi/(200*omega),E0=.5*kt*A*A;
 double error=0;
 SupportLaw support=[&](const auto&,double){return std::vector<Load>{{{0,-kn*delta,0},0}};};
 for(int j=0;j<4000;++j){step.advance(b,dem,law,search,n,w,n,w,e,{0},j*dt,dt,support);
  error=std::max(error,std::abs((kineticEnergy(b)+law.tangentialEnergy())/E0-1));}
 require(error<3e-4,"sticking tangential/rotational energy bound");
 std::cout<<"PASS tangential/rotational elastic oscillator; max_relative_energy_error="<<std::setprecision(16)<<error<<"\n";
}
void history_and_rollback(){
 std::vector<Ball> n={{{-1,0,0},.2},{{1,0,0},.2}},g0={{{0,.301,0},.1}},g1={{{.001,.299,0},.1}};
 std::vector<Motion> v={{{.01,-.02,0},0,0}},w(2);std::vector<Edge> e={{0,1}};
 Search search(Mode::direct,0,1e-12);PlanarLaw law(1000,100,0,.5);
 auto hits=search.run(g1,n,e);law.advanceHistory(hits,g0,v,n,w,g1,v,n,w,e,{0},.1);
 require(std::abs(law.tangentialHistory(0,0)+.0005)<1e-14,"active-fraction midpoint slip");
 const double xi=law.tangentialHistory(0,0);
 for(int k=0;k<10;++k)law.step(hits,g1,v,n,w,e,{0},0.);
 require(law.tangentialHistory(0,0)==xi,"query must not update history");
 auto duplicate=hits;duplicate.push_back(hits[0]);bool rejected=false;
 try{law.step(duplicate,g1,v,n,w,e,{0},.1);}catch(const std::invalid_argument&){rejected=true;}
 require(rejected&&law.tangentialHistory(0,0)==xi,"duplicate rejection/transaction");
 law.advanceHistory({},g1,v,n,w,g0,v,n,w,e,{0},.1);require(law.historySize()==0,"release clears history");
 law.advanceHistory(hits,g0,v,n,w,g1,v,n,w,e,{0},.1);require(std::abs(law.tangentialHistory(0,0)-xi)<1e-14,"recontact resets history");
 std::vector<ibdem::Body> bodies={ibdem::disk(7,{0,.299},.1,2650)};ibdem::DEM dem;DryRootStepper step;
 auto before=bodies;auto before_law=law;const auto before_count=dem.force_evaluations;step.max_kick_iterations=1;
 try{step.advance(bodies,dem,law,search,n,w,n,w,e,{0},0,.001);rejected=false;}catch(const std::runtime_error&){rejected=true;}
 require(rejected&&bodies[0].x.y==before[0].x.y&&bodies[0].v.y==before[0].v.y&&
 dem.force_evaluations==before_count&&law.tangentialHistory(0,0)==before_law.tangentialHistory(0,0),"failed kick rollback");
 step.max_kick_iterations=64;step.advance(bodies,dem,law,search,n,w,n,w,e,{0},0,1e-5);
 bodies[0].id=9;rejected=false;try{step.advance(bodies,dem,law,search,n,w,n,w,e,{0},1e-5,1e-5);}catch(const std::invalid_argument&){rejected=true;}
 require(rejected,"changed grain identity must not silently reuse history");
 std::cout<<"PASS active-fraction slip, read-only force query, duplicate input, release/recontact, rollback, stable identity\n";
}
int main(int argc,char**argv){
 std::ofstream metrics,series;if(argc==2){metrics.open(std::string(argv[1])+"/oscillator_summary.csv");series.open(std::string(argv[1])+"/oscillator_history.csv");require(bool(metrics)&&bool(series),"output directory");}
 std::ostream& out=argc==2?metrics:std::cout;
 out<<"method,steps_per_period,damping_ratio,max_relative_energy_error,max_displacement_error_over_A,final_state_error_over_A,max_kick_power_error_over_E0\n"<<std::setprecision(16);
 if(series)series<<"method,steps_per_period,damping_ratio,time_s,displacement_m,exact_displacement_m,energy_over_E0\n";
 double previous_energy=0,previous_state=0;
 for(int per:{100,200,400,800})for(bool corrected:{false,true}){
  auto r=oscillator(per,corrected,0,series?&series:nullptr);
  out<<(corrected?"symmetric":"held")<<','<<per<<",0,"<<r.energy<<','<<r.position<<','<<r.final_state<<','<<r.power<<'\n';
  if(corrected){if(per>=200){require(r.energy<3e-4,"normal energy bound");require(std::log2(previous_energy/r.energy)>1.8,"energy order");require(std::log2(previous_state/r.final_state)>1.8,"phase order");}require(r.power<1e-10,"half-kick work identity");previous_energy=r.energy;previous_state=r.final_state;}
 }
 for(int per:{100,200,400}){auto r=oscillator(per,true,.1,series?&series:nullptr);
  out<<"symmetric,"<<per<<",0.1,"<<r.energy<<','<<r.position<<','<<r.final_state<<','<<r.power<<'\n';
  if(per>=200)require(r.position<.002,"damped oscillator displacement");}
 tangential_oscillator();history_and_rollback();std::cout<<"PASS conservative/damped oscillator, convergence and kick work\n";
}
