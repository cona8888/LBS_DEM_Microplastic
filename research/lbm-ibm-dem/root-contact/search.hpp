#pragma once
#include "geometry.hpp"
#include <numeric>
#include <vector>
namespace rhizo {
struct Contact {int grain,edge; Hit h;};
struct Alert {int grain,edge; Event interval;};
enum class Mode { direct, tree, cached, automatic, scan };
class Search {
 struct Node{Box b;int l,r,i,j;};
 std::vector<Node> tree; std::vector<int> order; std::vector<Box> boxes;
 std::vector<Ball> oldg,oldn;std::vector<Edge> olde;
 std::vector<std::vector<int>> near;bool ready=false;size_t age=0;double width=0;
 int build(int i,int j){
  int k=int(tree.size());Box b=boxes[order[i]];for(int q=i+1;q<j;++q)b=hull(b,boxes[order[q]]);
  tree.push_back({b,-1,-1,i,j});if(j-i<=4)return k;
  V w=b.hi-b.lo;int ax=w.x>=w.y&&w.x>=w.z?0:(w.y>=w.z?1:2);int m=(i+j)/2;
  std::nth_element(order.begin()+i,order.begin()+m,order.begin()+j,[&](int s,int t){return boxes[s].lo[ax]+boxes[s].hi[ax]<boxes[t].lo[ax]+boxes[t].hi[ax];});
  int l=build(i,m),r=build(m,j);tree[k].l=l;tree[k].r=r;return k;
 }
 template<class F> void visit(int k,Box b,F& f)const{auto& n=tree[k];if(!meets(n.b,b))return;if(n.l<0){for(int q=n.i;q<n.j;++q){int s=order[q];if(meets(boxes[s],b))f(s);}}else{visit(n.l,b,f);visit(n.r,b,f);}}
 static double drift(const std::vector<Ball>& a,const std::vector<Ball>& b){double d=0;for(size_t i=0;i<a.size();++i)d=std::max(d,len(a[i].p-b[i].p)+std::abs(a[i].r-b[i].r));return d;}
public:
 const double skin,eps; const Mode mode; size_t builds=0,tests=0;
 Search(Mode m,double skin_,double eps_):skin(skin_),eps(eps_),mode(m){if(!(skin>=0&&eps>=0&&std::isfinite(skin)&&std::isfinite(eps)))throw std::invalid_argument("bad search margin");}
 // Independent swept tree: calling this does not modify an endpoint neighbour cache.
 static std::vector<Alert> guard(const std::vector<Ball>& g,const std::vector<Ball>& G,const std::vector<Ball>& n,const std::vector<Ball>& N,const std::vector<Edge>& e,double tol,double fraction=1e-5){
  Search ix(Mode::tree,0,tol);if(g.size()!=G.size()||n.size()!=N.size()||!(fraction>=1e-12&&fraction<=1))throw std::invalid_argument("invalid sweep; split topology events");
  for(const auto* v:{&g,&G,&n,&N})for(auto x:*v)valid(x);
  std::vector<Alert> out;if(e.empty())return out;
  for(auto p:e){if(p[0]==p[1])throw std::invalid_argument("identical vertex indices");int a=p[0],b=p[1];ix.boxes.push_back(hull(hull(box(n.at(a)),box(N.at(a))),hull(box(n.at(b)),box(N.at(b)))));}
  ix.order.resize(e.size());std::iota(ix.order.begin(),ix.order.end(),0);ix.build(0,int(e.size()));
  for(size_t i=0;i<g.size();++i){auto test=[&](int s){auto p=e[s];auto ev=swept(n[p[0]],n[p[1]],g[i],N[p[0]],N[p[1]],G[i],tol,fraction);if(ev.possible)out.push_back({int(i),s,ev});};ix.visit(0,hull(box(g[i],tol),box(G[i],tol)),test);}
  return out;
 }
 std::vector<Contact> run(const std::vector<Ball>& g,const std::vector<Ball>& n,const std::vector<Edge>& e){
  for(auto x:g)valid(x);
  for(auto x:n)valid(x);
  std::vector<Span> spans;spans.reserve(e.size());for(auto p:e){if(p[0]<0||p[1]<0||size_t(p[0])>=n.size()||size_t(p[1])>=n.size()||p[0]==p[1])throw std::invalid_argument("invalid edge");spans.emplace_back(n[p[0]],n[p[1]]);}
  const Mode active=mode==Mode::automatic?(g.empty()||e.size()<=16/g.size()?Mode::direct:Mode::cached):mode;
  const bool indexed=active==Mode::tree||active==Mode::cached;
  bool comparable=active==Mode::cached&&ready&&olde==e&&oldg.size()==g.size()&&oldn.size()==n.size();
  ++age;double change=comparable?drift(g,oldg)+drift(n,oldn):0;
  const bool rebuild=indexed&&(active==Mode::tree||!comparable||change>=width);
  if(rebuild){width=(active==Mode::tree||(mode==Mode::automatic&&comparable&&change/age>=skin))?0:skin;age=0;}
  if(active==Mode::direct||active==Mode::scan)ready=false;
  if(active==Mode::scan){boxes.clear();for(auto p:e)boxes.push_back(hull(box(n[p[0]]),box(n[p[1]])));}
  if(rebuild){++builds;boxes.clear();for(auto p:e)boxes.push_back(hull(box(n[p[0]]),box(n[p[1]])));order.resize(e.size());std::iota(order.begin(),order.end(),0);tree.clear();if(!e.empty())build(0,int(e.size()));
   if(width>0){near.assign(g.size(),{});for(size_t i=0;i<g.size()&&!e.empty();++i){auto add=[&](int s){near[i].push_back(s);};visit(0,box(g[i],eps+width),add);std::sort(near[i].begin(),near[i].end());}}
   if(active==Mode::cached){oldg=g;oldn=n;olde=e;ready=true;}
  }
  tests=0;std::vector<Contact> out;std::vector<Contact> raw;
  for(size_t i=0;i<g.size();++i){raw.clear();auto check=[&](int s){++tests;Hit h=spans[s].query(g[i]);if(h.gap<=eps)raw.push_back({int(i),s,h});};
   if(active==Mode::direct){for(size_t s=0;s<e.size();++s)check(int(s));}else if(active==Mode::scan){Box b=box(g[i],eps);for(size_t s=0;s<e.size();++s)if(meets(b,boxes[s]))check(int(s));}else if(width==0){if(!e.empty())visit(0,box(g[i],eps),check);std::sort(raw.begin(),raw.end(),[](auto a,auto b){return a.edge<b.edge;});}else for(int s:near[i])check(s);
   // A shared endpoint ball is one physical feature. Suppress buried surface witnesses.
   auto end=[&](const Contact& c){return c.h.t==0?e[c.edge][0]:(c.h.t==1?e[c.edge][1]:-1);};
   for(auto c:raw){bool keep=true;int id=end(c);for(auto q:raw){if(c.edge==q.edge)continue;if(id>=0&&id==end(q)&&q.edge<c.edge){keep=false;break;}
     if(id>=0&&end(q)!=id&&(e[q.edge][0]==id||e[q.edge][1]==id)){keep=false;break;}
     if(c.h.regular&&spans[q.edge].query({c.h.root,0}).gap < -eps){keep=false;break;}}
    if(keep)out.push_back(c);
   }
  }return out;
 }
};
} // namespace rhizo
