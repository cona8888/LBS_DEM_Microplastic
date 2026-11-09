#include "traction.hpp"
#include <iostream>
#include <random>
using namespace rhizo;
void test(bool x){if(!x)throw std::logic_error("adversarial test failed");}
int main(){std::mt19937_64 rng(733);std::uniform_real_distribution<double> u(-1,1);int positive=0,alerts=0;
 for(int k=0;k<300;++k){std::vector<Ball> n={{{-.5,u(rng),0},.1},{{.5,u(rng),0},.1}},N=n;N[1].p.y+=u(rng);N[0].r+=.15;Ball g{{u(rng),u(rng),.05},.15},G=g;G.p.y+=1.5*u(rng);bool true_hit=false;
  for(int j=0;j<=400;++j){double t=j/400.;if(Span(mix(n[0],N[0],t),mix(n[1],N[1],t)).query(mix(g,G,t)).gap<0){true_hit=true;break;}}
  auto r=Search::guard({g},{G},n,N,{{0,1}},1e-12,1e-5);test(!true_hit||!r.empty());positive+=true_hit;alerts+=!r.empty();}
 std::cout<<"PASS 300 swept scenes; dense samples with penetration="<<positive<<"; possible-event alerts="<<alerts<<"\n";
 std::vector<Ball> n={{{-1,0,0},.2},{{1,0,0},.2}},g={{{.25,.299,0},.1}};std::vector<Edge> e={{0,1}};Search d(Mode::direct,0,1e-12);PlanarLaw law(5000,100,2,.5);std::vector<Motion> nv(2),gv(1);
 auto rotation=[](V p){return V{-p.y,p.x,0};};nv[0]={rotation(n[0].p),1,0};nv[1]={rotation(n[1].p),1,0};gv[0]={rotation(g[0].p),1,0};auto l=law.step(d.run(g,n,e),g,gv,n,nv,e,{0},.01);test(std::abs(l.grain[0].f.x)<1e-13&&std::abs(l.grain[0].f.y-5)<1e-12);
 std::vector<Ball> fork={{{0,0,0},.05},{{1,1,0},.05},{{1,-1,0},.05}},fork_g={{{.14,0,0},.0501}};std::vector<Edge> fe={{0,1},{0,2}};auto fh=d.run(fork_g,fork,fe);test(fh.size()==2);bool caught=false;try{law.step(fh,fork_g,gv,fork,std::vector<Motion>(3),fe,{0,0},.01);}catch(const std::domain_error&){caught=true;}test(caught);
 auto ll=law.step(fh,fork_g,gv,fork,std::vector<Motion>(3),fe,{0,1},.01);test(ll.grain[0].f.x>0);
 Ball a{{0,0,0},1},b{{1,0,0},2-1e-12};auto h=Span(a,b).query({{.1,1e-8,0},.01});test(std::isfinite(h.gap));caught=false;try{d.run({{{0,0,0},-1}},n,e);}catch(const std::invalid_argument&){caught=true;}test(caught);
 std::cout<<"PASS common rigid rotation, fork friction guard, distinct strands, near-contained taper and invalid input\n";
}
