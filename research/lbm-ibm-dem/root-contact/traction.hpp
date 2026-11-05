#pragma once
#include "search.hpp"
#include <map>
#include <set>
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
  std::set<std::pair<int,int>> seen;
  for(auto c:hits){
   if(c.grain<0||size_t(c.grain)>=g.size()||c.edge<0||size_t(c.edge)>=e.size()||
      !seen.emplace(c.grain,c.edge).second)
       throw std::invalid_argument("invalid or duplicate contact identity");
   for(int j:e[c.edge])if(j<0||size_t(j)>=n.size())throw std::invalid_argument("invalid contact node");
   Hit h=c.h;
   if(!std::isfinite(h.gap)||!std::isfinite(h.t)||h.t<0||h.t>1)
       throw std::invalid_argument("invalid contact geometry");
   if(h.gap>=0)continue;
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
 // One accepted history increment, separate from non-mutating force queries.
 // Endpoint gaps bound the active fraction of a newly formed contact. This is
 // an event approximation; curved trajectories and stick/slip require dt studies.
 void advanceHistory(const std::vector<Contact>& end_hits,
   const std::vector<Ball>& g0,const std::vector<Motion>& v0,
   const std::vector<Ball>& n0,const std::vector<Motion>& w0,
   const std::vector<Ball>& g1,const std::vector<Motion>& v1,
   const std::vector<Ball>& n1,const std::vector<Motion>& w1,
   const std::vector<Edge>& e,const std::vector<int>& strand,double dt){
  if(!(dt>0)||!std::isfinite(dt)||g0.size()!=g1.size()||n0.size()!=n1.size()||
      v0.size()!=g0.size()||v1.size()!=g1.size()||w0.size()!=n0.size()||w1.size()!=n1.size())
   throw std::invalid_argument("history interval/state size");
  // Validate endpoint laws and all supplied hits without advancing any history.
  step(end_hits,g1,v1,n1,w1,e,strand,0.0);
  decltype(hist) next;
  if(kt*mu==0){hist.swap(next);return;}
  auto blend=[](Motion a,Motion b,double t){return Motion{a.v*(1-t)+b.v*t,a.omega*(1-t)+b.omega*t,a.rdot*(1-t)+b.rdot*t};};
  auto spin=[](V r,double w){return V{-w*r.y,w*r.x,0};};
  for(const auto& c:end_hits){
   if(c.h.gap>=0)continue;
   const int i=c.grain,a=e[c.edge][0],b=e[c.edge][1];const auto key=std::make_pair(i,strand[c.edge]);
   Hit h0=Span(n0[a],n0[b]).query(g0[i]);
   const double fraction=h0.gap>0?std::clamp(-c.h.gap/(h0.gap-c.h.gap),0.,1.):1.;
   const double time=1-.5*fraction;
   Ball ga=mix(g0[i],g1[i],time),na=mix(n0[a],n1[a],time),nb=mix(n0[b],n1[b],time);
   Hit hm=Span(na,nb).query(ga);
   if(!hm.regular)throw std::domain_error("undefined history midpoint normal");
   Motion vg=blend(v0[i],v1[i],time),va=blend(w0[a],w1[a],time),vb=blend(w0[b],w1[b],time);
   V p=(hm.root+hm.grain)*.5,axis=mix(na,nb,hm.t).p,tangent={-hm.n.y,hm.n.x,0};
   V vr=va.v*(1-hm.t)+vb.v*hm.t+spin(p-axis,va.omega*(1-hm.t)+vb.omega*hm.t)+hm.n*(va.rdot*(1-hm.t)+vb.rdot*hm.t);
   V relative=vg.v+spin(p-ga.p,vg.omega)-hm.n*vg.rdot-vr;
   // End normal load determines the endpoint Coulomb bound.
   const double s=c.h.t;V ep=(c.h.root+c.h.grain)*.5,ea=mix(n1[a],n1[b],s).p;
   V evr=w1[a].v*(1-s)+w1[b].v*s+spin(ep-ea,w1[a].omega*(1-s)+w1[b].omega*s)+c.h.n*(w1[a].rdot*(1-s)+w1[b].rdot*s);
   V edv=v1[i].v+spin(ep-g1[i].p,v1[i].omega)-c.h.n*v1[i].rdot-evr;
   double fn=std::max(0.,-kn*c.h.gap-cn*dot(edv,c.h.n));if(fn==0)continue;
   double xi=0;auto old=hist.find(key);
   if(h0.gap<=0&&old!=hist.end()){auto last=old->second.e;
    if(last[0]==a||last[0]==b||last[1]==a||last[1]==b)xi=old->second.xi;}
   xi=std::clamp(xi+fraction*dt*dot(relative,tangent),-mu*fn/kt,mu*fn/kt);
   if(!next.emplace(key,State{e[c.edge],xi}).second)
    throw std::domain_error("multiple history patches on a strand");
  }
  hist.swap(next);
 }
 double tangentialHistory(int grain,int strand)const{auto q=hist.find({grain,strand});return q==hist.end()?0:q->second.xi;}
 double tangentialEnergy()const{double v=0;for(const auto& q:hist)v+=.5*kt*q.second.xi*q.second.xi;return v;}
 size_t historySize()const{return hist.size();}
 void reset(){hist.clear();}
};
} // namespace rhizo
