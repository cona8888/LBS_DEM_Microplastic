#pragma once
// Sphere vs convex hull of two endpoint balls. Length units must be consistent.
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>
namespace rhizo {
struct V { double x=0,y=0,z=0; double operator[](int i)const{return i==0?x:(i==1?y:z);} };
inline V operator+(V a,V b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
inline V operator-(V a,V b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
inline V operator*(V a,double s){return {a.x*s,a.y*s,a.z*s};}
inline double dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline double len(V a){return std::sqrt(dot(a,a));}
inline V cross(V a,V b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
struct Ball { V p; double r; };
inline void valid(Ball a){if(!(std::isfinite(a.p.x)&&std::isfinite(a.p.y)&&std::isfinite(a.p.z)&&std::isfinite(a.r)&&a.r>=0))throw std::invalid_argument("invalid position or radius");}
inline Ball mix(Ball a,Ball b,double t){return {a.p+(b.p-a.p)*t,a.r+t*(b.r-a.r)};}
using Edge=std::array<int,2>;
struct Hit {double gap,t; V n,root,grain; bool regular;};
struct Span {
 Ball a,b; V d,e; double L,dr,slope; bool nested;
 Span(Ball a_,Ball b_):a(a_),b(b_),d(b.p-a.p),e{},L(len(d)),dr(b.r-a.r),slope(0),nested(L<=std::abs(dr)){
  if(!nested){e=d*(1/L);slope=dr/std::sqrt((L-std::abs(dr))*(L+std::abs(dr)));}
 }
 Hit query(Ball g)const{
  V v=g.p-a.p; double t;
  if(nested)t=dr>0?1:0;
  else {double h=dot(v,e);t=std::clamp((h+slope*len(v-e*h))/L,0.,1.);}
  Ball c=mix(a,b,t); V w=g.p-c.p; double m=len(w);
  V n=m>0?w*(1/m):V{};
  return {m-c.r-g.r,t,n,c.p+n*c.r,g.p-n*g.r,m>0};
 }
};
struct Box {V lo,hi;};
inline Box box(Ball g,double extra=0){double s=g.r+extra;V r{s,s,s};return {g.p-r,g.p+r};}
inline Box hull(Box a,Box b){return {{std::min(a.lo.x,b.lo.x),std::min(a.lo.y,b.lo.y),std::min(a.lo.z,b.lo.z)},{std::max(a.hi.x,b.hi.x),std::max(a.hi.y,b.hi.y),std::max(a.hi.z,b.hi.z)}};}
inline bool meets(Box a,Box b){for(int j=0;j<3;++j)if(a.hi[j]<b.lo[j]||a.lo[j]>b.hi[j])return false;return true;}
struct Event {bool possible; double lo,hi;};
// Conservative POSSIBLE first-contact interval, not an impact impulse or an exact TOI.
// Endpoints/radii interpolate linearly. Nonlinear trajectories require subinterval bounds.
inline Event swept(Ball a,Ball b,Ball g,Ball A,Ball B,Ball G,double tol,double fraction=1e-5){
 for(auto x:{a,b,g,A,B,G})valid(x);
 if(!(tol>=0&&std::isfinite(tol)&&fraction>=1e-12&&fraction<=1))throw std::invalid_argument("bad CCD tolerances");
 double k=std::max(len((A.p-a.p)-(G.p-g.p))+std::abs((A.r-a.r)+(G.r-g.r)),len((B.p-b.p)-(G.p-g.p))+std::abs((B.r-b.r)+(G.r-g.r)));
 auto gap=[&](double t){return Span(mix(a,A,t),mix(b,B,t)).query(mix(g,G,t)).gap;};
 if(gap(0)<=tol)return {true,0,0};
 if(!meets(hull(box(g,tol),box(G,tol)),hull(hull(box(a),box(A)),hull(box(b),box(B)))))return {false,1,1};
 auto search=[&](auto&& self,double l,double r)->Event{double m=.5*(l+r);if(gap(m)-k*(r-l)*.5>tol)return {false,1,1};if(r-l<=fraction)return {true,l,r};Event v=self(self,l,m);return v.possible?v:self(self,m,r);};
 return search(search,0,1);
}
} // namespace rhizo
