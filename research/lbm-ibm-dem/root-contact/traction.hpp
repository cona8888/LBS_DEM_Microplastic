#pragma once
#include "search.hpp"
#include <map>
namespace rhizo {
// 2D per unit depth. Supply material velocities, NOT the tip growth speed on every node.
struct Motion {V v;double omega=0,rdot=0;};
struct Load {V f;double torque=0;};
struct Loads {std::vector<Load> grain,node;};
class PlanarLaw {
 struct State{Edge e;double xi;};
 std::map<std::pair<int,int>,State> hist;
public:
 double kn,kt,cn,mu,max_relative_overlap=.05;
 PlanarLaw(double k,double t,double c,double f):kn(k),kt(t),cn(c),mu(f){}
 Loads step(const std::vector<Contact>& hits,const std::vector<Ball>& g,const std::vector<Motion>& gv,const std::vector<Ball>& n,const std::vector<Motion>& nv,const std::vector<Edge>& e,const std::vector<int>& strand,double dt){
  for(double v:{dt,kn,kt,cn,mu,max_relative_overlap})if(!std::isfinite(v)||v<0)throw std::invalid_argument("invalid force parameter");
  if(gv.size()!=g.size()||nv.size()!=n.size()||strand.size()!=e.size())throw std::invalid_argument("motion/topology size");
  auto planar=[](const std::vector<Ball>& b,const std::vector<Motion>& v){for(size_t i=0;i<b.size();++i){valid(b[i]);valid({v[i].v,0});if(b[i].p.z!=0||v[i].v.z!=0||!std::isfinite(v[i].omega)||!std::isfinite(v[i].rdot))throw std::invalid_argument("nonplanar geometry or invalid motion");}};
  planar(g,gv);planar(n,nv);
  Loads out{std::vector<Load>(g.size()),std::vector<Load>(n.size())};decltype(hist) next;
  auto spin=[](V r,double w){return V{-w*r.y,w*r.x,0};};
  for(auto c:hits){Hit h=c.h;if(h.gap>=0)continue;
   if(!h.regular||std::abs(h.n.z)>1e-10)throw std::domain_error("undefined or nonplanar normal");
   int i=c.grain,a=e.at(c.edge)[0],b=e.at(c.edge)[1];double s=h.t;
   if(-h.gap>max_relative_overlap*std::min(g.at(i).r,mix(n.at(a),n.at(b),s).r))throw std::domain_error("excessive overlap: reduce step or repair geometry");
   V t={-h.n.y,h.n.x,0};
   V p=(h.root+h.grain)*.5,axis=mix(n[a],n[b],s).p;
   V vr=nv[a].v*(1-s)+nv[b].v*s+spin(p-axis,nv[a].omega*(1-s)+nv[b].omega*s)+h.n*(nv[a].rdot*(1-s)+nv[b].rdot*s);
   V dv=gv[i].v+spin(p-g[i].p,gv[i].omega)-h.n*gv[i].rdot-vr;
   double fn=std::max(0.,-kn*h.gap-cn*dot(dv,h.n));if(fn==0)continue;
   auto key=std::make_pair(i,strand[c.edge]);double xi=0;auto old=hist.find(key);
   if(kt*mu>0&&old!=hist.end()){auto last=old->second.e;if(last[0]==a||last[0]==b||last[1]==a||last[1]==b)xi=old->second.xi;}
   double ft=std::clamp(-kt*(xi+dt*dot(dv,t)),-mu*fn,mu*fn);
   if(kt*mu>0&&!next.emplace(key,State{e[c.edge],-ft/kt}).second)throw std::domain_error("multiple friction patches on one strand; assign distinct material strands or implement patch tracking");
   V f=h.n*fn+t*ft;out.grain[i].f=out.grain[i].f+f;out.grain[i].torque+=cross(p-g[i].p,f).z;
   for(auto w:{std::make_pair(a,1-s),std::make_pair(b,s)}){out.node[w.first].f=out.node[w.first].f-f*w.second;out.node[w.first].torque-=cross(p-axis,f).z*w.second;}
  }if(dt>0)hist.swap(next);return out;
 }
 void reset(){hist.clear();}
};
} // namespace rhizo
