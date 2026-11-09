#include "traction.hpp"
#include <iostream>
#include <random>
using namespace rhizo;
void req(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
bool eq(double x,double y,double tol=1e-10){return std::abs(x-y)<=tol;}
// Independent long-double convex 1-D minimisation, including both endpoints.
long double oracle(Ball a,Ball b,Ball g){auto f=[&](long double t){long double sq=0;for(int j=0;j<3;++j){long double d=(long double)g.p[j]-a.p[j]-t*((long double)b.p[j]-a.p[j]);sq+=d*d;}return std::sqrt(sq)-a.r-t*((long double)b.r-a.r)-g.r;};long double l=0,r=1;for(int j=0;j<128;++j){long double u=(2*l+r)/3,v=(l+2*r)/3;if(f(u)<f(v))r=v;else l=u;}return std::min({f(0),f(1),f((l+r)/2)});}
void same(const std::vector<Contact>& a,const std::vector<Contact>& b){req(a.size()==b.size(),"count mismatch");for(size_t i=0;i<a.size();++i)req(a[i].grain==b[i].grain&&a[i].edge==b[i].edge&&a[i].h.gap==b[i].h.gap&&len(a[i].h.n-b[i].h.n)==0,"contact mismatch");}
int main(){
 std::mt19937_64 rng(20261102);std::uniform_real_distribution<double> u(-1,1);auto v=[&](){return V{u(rng),u(rng),u(rng)};};double err=0;
 for(int i=0;i<12000;++i){Ball a{v(),.01+std::abs(u(rng))},b{v(),.01+std::abs(u(rng))},g{v(),.01+std::abs(u(rng))};if(i%17==0)b.p=a.p;if(i%19==0)b.r=a.r;auto h=Span(a,b).query(g);err=std::max(err,double(std::abs(h.gap-oracle(a,b,g))));req(eq(Span(b,a).query(g).gap,h.gap),"endpoint order");if(h.regular)req(len(h.grain-h.root-h.n*h.gap)<1e-11,"witness identity");}
 req(err<1e-11,"scalar oracle");std::cout<<"PASS 12000 independent tapered-gap queries; maximum error="<<err<<" coordinate units\n";
 std::vector<Ball> n={{{-1,0,0},.2},{{0,0,0},.2},{{1,0,0},.2}},g={{{0,.29,0},.1}};std::vector<Edge> e={{0,1},{1,2}};
 Search cache(Mode::cached,.05,1e-12),ref(Mode::direct,0,1e-12);auto hits=cache.run(g,n,e);req(hits.size()==1,"joint doubled");g[0].p.x=1e-7;req(cache.run(g,n,e).size()==1,"near-joint doubled");
 g[0].p={2,0,0};req(cache.run(g,n,e).empty(),"initial clearance");n[2].r=.95;req(cache.run(g,n,e).size()==1,"growth omitted");n.push_back({{2.5,0,0},.1});e.push_back({2,3});same(cache.run(g,n,e),ref.run(g,n,e));
 std::vector<Ball> fork={{{0,0,0},.05},{{1,1,0},.05},{{1,-1,0},.05}};std::vector<Edge> branches={{0,1},{0,2}};req(ref.run({{{.14,0,0},.06}},fork,branches).size()==2,"lost separate branch contacts");
 std::vector<Ball> cloud,root;std::vector<Edge> edges;for(int i=0;i<120;++i)cloud.push_back({v(),.085});for(int j=0;j<35;++j){root.push_back({v(),.03});if(j)edges.push_back({j-1,j});}
 for(int t=0;t<60;++t){for(auto& x:cloud)x.p=x.p+v()*.002;root[10].r+=.0006;if(t==30){root.push_back({v(),.05});edges.push_back({11,35});}same(cache.run(cloud,root,edges),ref.run(cloud,root,edges));}
 std::cout<<"PASS seam, fork, thickness, topology and 60 moving 3D frames\n";
 Ball a{{-1,0,0},.2},b{{1,0,0},.2},f{{0,1,0},.1},F{{0,-1,0},.1};auto event=swept(a,b,f,a,b,F,1e-12,1e-6);req(event.possible&&event.lo<=.35&&event.hi>=.35-2e-6,"swept entry");F.p.y=.31;req(!swept(a,b,f,a,b,F,1e-12).possible,"swept miss");
 Ball B=b;B.r=1.1;f={{1,.8,0},.1};req(swept(a,b,f,a,B,f,1e-12).possible,"swept growth");
 n.resize(3);n[2].r=.2;e.resize(2);g[0]={{-.002,.29,0},.1};PlanarLaw law(1000,100,0,.5);law.max_relative_overlap=.15;std::vector<Motion> ng(3),gg(1);gg[0].v={.01,0,0};
 auto first=law.step(ref.run(g,n,e),g,gg,n,ng,e,{1,1},.1);g[0].p.x=.002;auto load=law.step(ref.run(g,n,e),g,gg,n,ng,e,{1,1},.1);
 req(eq(first.grain[0].f.x,-.1)&&eq(load.grain[0].f.x,-.2),"seam slip history");V net=load.grain[0].f;double torque=cross(g[0].p,net).z+load.grain[0].torque;for(int j=0;j<3;++j){net=net+load.node[j].f;torque+=cross(n[j].p,load.node[j].f).z+load.node[j].torque;}req(len(net)<1e-12&&std::abs(torque)<1e-12,"wrench balance");
 gg[0].v.x=100;load=law.step(ref.run(g,n,e),g,gg,n,ng,e,{1,1},.1);req(eq(std::abs(load.grain[0].f.x),.5*load.grain[0].f.y),"Coulomb");law.step({},g,gg,n,ng,e,{1,1},.1);gg[0].v.x=0;load=law.step(ref.run(g,n,e),g,gg,n,ng,e,{1,1},.1);req(eq(load.grain[0].f.x,0),"release resets history");
 std::cout<<"PASS swept translation, swept radius, seam history, force/torque, Coulomb and release\n";
}
