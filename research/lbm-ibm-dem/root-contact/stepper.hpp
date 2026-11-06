#pragma once
// Symmetric dry root/native-DEM splitting. No modification of the native solver.
#include "traction.hpp"
#include "dem.hpp"
#include <functional>
namespace rhizo {
struct DryStepStats {
 int kick_iterations=0;
 double kick_power_residual=0,root_work=0;
 Loads endpoint;
};
using SupportLaw=std::function<std::vector<Load>(const std::vector<ibdem::Body>&,double)>;
inline std::vector<Ball> grainGeometry(const std::vector<ibdem::Body>& b){
 std::vector<Ball> v;v.reserve(b.size());for(const auto& x:b)v.push_back({{x.x.x,x.x.y,0},x.contactRadius()});return v;
}
inline std::vector<Motion> grainMotion(const std::vector<ibdem::Body>& b){
 std::vector<Motion> v;v.reserve(b.size());for(const auto& x:b)v.push_back(x.fixed?Motion{}:Motion{{x.v.x,x.v.y,0},x.omega,0});return v;
}
inline double kineticEnergy(const std::vector<ibdem::Body>& b){double k=0;for(const auto& x:b)if(!x.fixed)k+=.5*x.mass*ibdem::dot(x.v,x.v)+.5*x.inertia*x.omega*x.omega;return k;}
class DryRootStepper {
 std::vector<int> ids;std::vector<Edge> topology;std::vector<int> material;
 bool initialized=false;
public:
 double absolute_velocity_tolerance=1e-13,relative_velocity_tolerance=1e-10;
 int max_kick_iterations=64;
 void reset(){ids.clear();topology.clear();material.clear();initialized=false;}
 // Prescribed root geometry/motion at both endpoints. Node identity and topology
 // are constant during a step. Remeshing needs explicit history remapping/reset.
 DryStepStats advance(std::vector<ibdem::Body>& bodies,ibdem::DEM& dem,
   PlanarLaw& law,Search& search,const std::vector<Ball>& n0,const std::vector<Motion>& w0,
   const std::vector<Ball>& n1,const std::vector<Motion>& w1,const std::vector<Edge>& e,
   const std::vector<int>& strand,double time,double dt,const SupportLaw& support={}){
  if(!(dt>0)||!std::isfinite(dt)||!std::isfinite(time)||n0.size()!=n1.size()||
    w0.size()!=n0.size()||w1.size()!=n1.size()||strand.size()!=e.size()||
    max_kick_iterations<1||!(absolute_velocity_tolerance>0)||!(relative_velocity_tolerance>=0)||
    !std::isfinite(absolute_velocity_tolerance)||!std::isfinite(relative_velocity_tolerance))
   throw std::invalid_argument("invalid dry step controls");
  std::vector<int> current;for(const auto& b:bodies)current.push_back(b.id);
  if(initialized&&(current!=ids||e!=topology||strand!=material))
   throw std::invalid_argument("identity/topology changed: remap histories before restart");
  // Physical state is transactional. Failed iterations never commit slip or motion.
  auto trial=bodies;auto td=dem;auto tl=law;DryStepStats stats;
  td.evaluate(trial,0.0);
  auto kick=[&](const std::vector<Ball>& nodes,const std::vector<Motion>& motion,double at){
   const auto old=trial;auto guess=trial;const auto geometry=grainGeometry(old);
   const auto hits=search.run(geometry,nodes,e);const double h=dt*.5;
   for(int k=0;k<max_kick_iterations;++k){
    auto mid=old;for(size_t i=0;i<mid.size();++i)if(!mid[i].fixed){mid[i].v=(old[i].v+guess[i].v)*.5;mid[i].omega=(old[i].omega+guess[i].omega)*.5;}
    auto loads=tl.step(hits,geometry,grainMotion(mid),nodes,motion,e,strand,0.0);
    std::vector<Load> extra= support?support(mid,at):std::vector<Load>(old.size());
    if(extra.size()!=old.size())throw std::invalid_argument("support load size");
    auto next=old;double residual=0,scale=0,work=0;
    for(size_t i=0;i<old.size();++i){valid({extra[i].f,0});if(!std::isfinite(extra[i].torque)||extra[i].f.z!=0)throw std::invalid_argument("invalid planar support");
     if(old[i].fixed)continue;
     V f=loads.grain[i].f+extra[i].f;double torque=loads.grain[i].torque+extra[i].torque;
     next[i].v+=ibdem::Vec2{f.x,f.y}*(h/old[i].mass);next[i].omega+=h*torque/old[i].inertia;
     residual=std::max({residual,ibdem::norm(next[i].v-guess[i].v),old[i].radius*std::abs(next[i].omega-guess[i].omega)});
     scale=std::max({scale,ibdem::norm(next[i].v),ibdem::norm(old[i].v),old[i].radius*std::abs(next[i].omega)});
     work+=h*(f.x*mid[i].v.x+f.y*mid[i].v.y+torque*mid[i].omega);
    }
    ++stats.kick_iterations;
    if(!std::isfinite(residual))throw std::runtime_error("nonfinite root kick");
    if(residual<=absolute_velocity_tolerance+relative_velocity_tolerance*scale){
     stats.kick_power_residual+=std::abs(kineticEnergy(next)-kineticEnergy(old)-work);
     double power=0;for(size_t i=0;i<nodes.size();++i)power-=dot(loads.node[i].f,motion[i].v)+loads.node[i].torque*motion[i].omega;
     // Radius changes are active material sources, not a translational velocity.
     for(const auto& c:hits){double rate=motion[e[c.edge][0]].rdot*(1-c.h.t)+motion[e[c.edge][1]].rdot*c.h.t;
      // This port has at most one root patch per grain/material strand. For
      // multipatch radial work use per-contact loads; reject ambiguous geometry.
      if(rate!=0){size_t count=0;for(const auto& z:hits)count+=z.grain==c.grain;
       if(count!=1)throw std::domain_error("multipatch radial actuation work needs per-contact loads");
       power+=dot(loads.grain[c.grain].f,c.h.n)*rate;}}
     stats.root_work+=h*power;trial=std::move(next);return;
    }
    guess=std::move(next);
   }
   throw std::runtime_error("root velocity kick did not converge; reduce timestep");
  };
  kick(n0,w0,time);
  const auto drift0=trial;
  td.advance(trial,dt,1); // Native disk forces/history; no frozen root force.
  auto g0=grainGeometry(drift0),g1=grainGeometry(trial);
  const auto end_hits=search.run(g1,n1,e);
  tl.advanceHistory(end_hits,g0,grainMotion(drift0),n0,w0,g1,grainMotion(trial),n1,w1,e,strand,dt);
  kick(n1,w1,time+dt);
  td.evaluate(trial,0.0); // Refresh diagnostics at accepted velocity, no slip increment.
  stats.endpoint=tl.step(end_hits,g1,grainMotion(trial),n1,w1,e,strand,0.0);
  bodies=std::move(trial);dem=std::move(td);law=std::move(tl);
  ids=std::move(current);topology=e;material=strand;initialized=true;
  return stats;
 }
};
} // namespace rhizo
