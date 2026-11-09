#include "search.hpp"
#include <chrono>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>
using namespace rhizo;
struct Frame{std::vector<Ball> g,n;std::vector<Edge> e;};
std::vector<Frame> scene(int G,int S,bool mobile){
 std::mt19937_64 rng(45678);std::uniform_real_distribution<double> u(-1,1);Frame s;int side=int(std::ceil(std::cbrt(G)));double dx=.0008,W=side*dx;
 for(int i=0;i<G;++i)s.g.push_back({{dx*(i%side+.12*u(rng)),dx*((i/side)%side+.12*u(rng)),dx*(i/(side*side)+.12*u(rng))},dx*(.34+.08*u(rng))});
 for(int i=0;i<S;){int count=std::min(12,S-i);V p{.04*W,(.50+.40*u(rng))*W,(.50+.40*u(rng))*W};s.n.push_back({p,.00050});for(int j=0;j<count;++j){int a=int(s.n.size())-1;p=p+V{.85*W/count,.00028*u(rng),.00028*u(rng)};s.n.push_back({p,.00050-.00024*(j+1)/count});s.e.push_back({a,a+1});++i;}}
 std::vector<Frame> frames;for(int k=0;k<10;++k){for(auto& x:s.g)x.p.y+=mobile?.00016:.000001;for(size_t j=0;j<s.n.size();++j){s.n[j].p.z+=.000001*std::sin(j);s.n[j].r+=.000001;}if(k==5){s.n.back().p.x+=.00015;}frames.push_back(s);}return frames;
}
int main(){using Clock=std::chrono::steady_clock;std::cout<<"motion,grains,segments,frames,repeats,mode,median_ms_per_frame,min_ms_per_frame,max_ms_per_frame,search_builds_per_run,narrow_tests_per_run,contact_instances_per_run\n"<<std::setprecision(9);
 for(bool mobile:{false,true})for(auto size:{std::make_pair(1,1),{32,4},{512,24},{4096,96},{16384,256}}){auto frames=scene(size.first,size.second,mobile);std::vector<std::vector<Contact>> gold;Search oracle(Mode::direct,0,1e-12);for(auto& f:frames)gold.push_back(oracle.run(f.g,f.n,f.e));
 const Mode modes[]={Mode::direct,Mode::tree,Mode::cached,Mode::automatic,Mode::scan};const char* names[]={"direct","tree","cached","auto","scan"};std::array<std::vector<double>,5> times;std::array<size_t,5> builds{},tests{},hits{};
 for(int rep=0;rep<5;++rep)for(int m=0;m<5;++m){int j=(m+rep)%5;Search search(modes[j],.0001,1e-12);double elapsed=0;size_t total=0,count=0;
 for(size_t k=0;k<frames.size();++k){auto& f=frames[k];auto start=Clock::now();auto r=search.run(f.g,f.n,f.e);elapsed+=std::chrono::duration<double,std::milli>(Clock::now()-start).count();total+=search.tests;count+=r.size();if(r.size()!=gold[k].size())throw std::logic_error("mismatched count");for(size_t i=0;i<r.size();++i){auto& q=gold[k][i];if(r[i].grain!=q.grain||r[i].edge!=q.edge||r[i].h.gap!=q.h.gap||len(r[i].h.n-q.h.n)!=0)throw std::logic_error("mismatched geometry");}}
 times[j].push_back(elapsed/frames.size());builds[j]=search.builds;tests[j]=total;hits[j]=count;}
 for(int j=0;j<5;++j){auto& a=times[j];std::sort(a.begin(),a.end());std::cout<<(mobile?"mobile":"slow")<<','<<size.first<<','<<size.second<<",10,5,"<<names[j]<<','<<a[2]<<','<<a[0]<<','<<a[4]<<','<<builds[j]<<','<<tests[j]<<','<<hits[j]<<'\n';}
 }}
