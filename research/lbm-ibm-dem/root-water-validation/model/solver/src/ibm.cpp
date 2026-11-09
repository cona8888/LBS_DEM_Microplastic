#include "ibm.hpp"
#include <algorithm>
#include <numeric>
#include <chrono>
#include <limits>
#include <sstream>

namespace ibdem {
namespace {
using Clock=std::chrono::steady_clock;
double seconds(Clock::time_point t){return std::chrono::duration<double>(Clock::now()-t).count();}
double inner(const std::vector<double>& a,const std::vector<double>& b){
    double s=0;for(size_t i=0;i<a.size();++i)s+=a[i]*b[i];return s;
}
double length(const std::vector<double>& a){return std::sqrt(inner(a,a));}
void axpy(std::vector<double>& a,double s,const std::vector<double>& b){for(size_t i=0;i<a.size();++i)a[i]+=s*b[i];}
DiskCellMoments quadrature(const std::unordered_map<int,DiskCellMoments>& c,int node){auto it=c.find(node);return it==c.end()?DiskCellMoments{}:it->second;}
double gram(const LBM& f,const Marker& a,const Marker& b){
    double value=0;int i=0,j=0;
    while(i<16&&j<16){if(a.node[i]==b.node[j]){value+=a.w[i]*b.w[j]/f.rho[a.node[i]];++i;++j;}else if(a.node[i]<b.node[j])++i;else ++j;}
    return value;
}
}
double IBM::kernel(double x){
    double r=std::abs(x);if(r<1)return (3-2*r+std::sqrt(std::max(0.0,1+4*r-4*r*r)))/8;
    if(r<2)return (5-2*r-std::sqrt(std::max(0.0,-7+12*r-4*r*r)))/8;
    return 0;
}
double IBM::disk_cell_area(Vec2 centre,double radius,int x,int y){
    return disk_cell_moments(centre,radius,x,y).area;
}
void IBM::build_geometry(const LBM& f,const std::vector<Body>& b){
    if(!std::isfinite(marker_spacing)||marker_spacing<1.2)throw std::invalid_argument("This prototype requires finite marker_spacing >= 1.2 to avoid redundant constraints");
    if(!std::isfinite(marker_retraction)||marker_retraction<0)throw std::invalid_argument("Marker retraction must be finite and nonnegative");
    for(size_t i=0;i<b.size();++i){
        const auto& p=b[i];
        if(!std::isfinite(p.x.x)||!std::isfinite(p.x.y)||!std::isfinite(p.v.x)||!std::isfinite(p.v.y)||!std::isfinite(p.angle)||!std::isfinite(p.omega)||!std::isfinite(p.mass)||!std::isfinite(p.inertia)||!std::isfinite(p.radius))throw std::invalid_argument("Non-finite rigid body state");
        if(b[i].mass<=0 || b[i].inertia<=0 || b[i].radius<=0)throw std::invalid_argument("Positive physical radius, mass and inertia required");
        if(marker_retraction>=p.radius)throw std::invalid_argument("Marker retraction must be smaller than every physical body radius");
        if(b[i].x.x-b[i].radius<2 || b[i].x.y-b[i].radius<2 || b[i].x.x+b[i].radius>f.nx-3 || b[i].x.y+b[i].radius>f.ny-3)
            throw std::runtime_error("Disk must remain two lattice cells inside the periodic domain; periodic particle wrapping is not implemented");
        for(size_t j=0;j<i;++j)if(norm(b[i].x-b[j].x)<b[i].radius+b[j].radius-1e-10)
            throw std::runtime_error("Wet overlap is unsupported: interior ownership and unresolved lubrication need validation. Dry DEM tests remain available.");
    }
    if(geometry_cache.size()!=b.size()||geometry_nx!=f.nx||geometry_ny!=f.ny){geometry_cache.assign(b.size(),{});chi.assign(b.size(),{});geometry_nx=f.nx;geometry_ny=f.ny;}
    markers.clear();active_nodes.clear();
    for(size_t k=0;k<b.size();++k){
        const auto& p=b[k];auto& cached=geometry_cache[k];
        const bool translated=cached.radius!=p.radius||cached.x.x!=p.x.x||cached.x.y!=p.x.y;
        const bool retraction_changed=cached.retraction!=marker_retraction;
        const bool changed=translated||cached.angle!=p.angle||cached.spacing!=marker_spacing||retraction_changed;
        if(retraction_changed)force_rebuild=true;
        // Count is tied to the physical circumference. Only the numerical
        // constraint location and its actual rigid-motion/torque arm retract.
        int count=std::max(8,static_cast<int>(std::ceil(2*pi*p.radius/marker_spacing)));
        const double marker_radius=p.radius-marker_retraction;
        if(changed){cached.points.clear();for(int m=0;m<count;++m){double angle=2*pi*m/count+p.angle;Marker a;a.body=k;a.r={marker_radius*std::cos(angle),marker_radius*std::sin(angle)};a.x=p.x+a.r;
            int bx=static_cast<int>(std::floor(a.x.x))-1,by=static_cast<int>(std::floor(a.x.y))-1;
            int z=0;for(int iy=0;iy<4;++iy)for(int ix=0;ix<4;++ix){int x=bx+ix,y=by+iy;a.node[z]=y*f.nx+x;a.w[z]=kernel(x-a.x.x)*kernel(y-a.x.y);++z;}
            cached.points.push_back(a);
        }}
        for(const auto& a:cached.points){markers.push_back(a);for(int node:a.node)active_nodes.push_back(node);}
        if(translated){chi[k].clear();for(int y=static_cast<int>(std::floor(p.x.y-p.radius-0.5));y<=static_cast<int>(std::ceil(p.x.y+p.radius+0.5));++y)
            for(int x=static_cast<int>(std::floor(p.x.x-p.radius-0.5));x<=static_cast<int>(std::ceil(p.x.x+p.radius+0.5));++x){auto q=disk_cell_moments(p.x,p.radius,x,y);if(q.area>1e-14)chi[k][y*f.nx+x]=q;}
        }
        cached.x=p.x;cached.angle=p.angle;cached.radius=p.radius;cached.spacing=marker_spacing;cached.retraction=marker_retraction;
    }
    std::sort(active_nodes.begin(),active_nodes.end());active_nodes.erase(std::unique(active_nodes.begin(),active_nodes.end()),active_nodes.end());
    for(auto& a:markers)for(int j=0;j<16;++j)a.active[j]=std::lower_bound(active_nodes.begin(),active_nodes.end(),a.node[j])-active_nodes.begin();
    interior_active.assign(b.size(),{});
    for(size_t k=0;k<b.size();++k)for(const auto& e:chi[k]){auto it=std::lower_bound(active_nodes.begin(),active_nodes.end(),e.first);if(it!=active_nodes.end()&&*it==e.first)interior_active[k].push_back({int(it-active_nodes.begin()),e.second});}
}
std::vector<InteriorMomentum> IBM::interior_momentum(const LBM& f,const std::vector<Body>& b) const{
    std::vector<InteriorMomentum> p(b.size());
    for(size_t k=0;k<b.size();++k)for(const auto& entry:chi[k]){int i=entry.first;Vec2 j=f.u[i]*f.rho[i];p[k].p+=j*entry.second.area;p[k].angular+=cross(entry.second.first,j);}
    return p;
}
void IBM::initialize(const LBM& f,const std::vector<Body>& b){build_geometry(f,b);old_interior=interior_momentum(f,b);hydrodynamic_impulse.assign(b.size(),{});initialized=true;previous_impulse.clear();blocks.clear();force_rebuild=true;last_prescribed=false;}
std::vector<double> IBM::apply_operator(const LBM& f,const std::vector<Body>& b,const std::vector<double>& in,bool compact) const{
    const int nm=markers.size();if(in.size()!=size_t(2*nm))throw std::invalid_argument("IBM impulse dimension mismatch");
    std::vector<Vec2> spread(compact?active_nodes.size():f.n);
    for(int m=0;m<nm;++m){Vec2 l{in[2*m],in[2*m+1]};const auto& a=markers[m];for(int z=0;z<16;++z)spread[compact?a.active[z]:a.node[z]]+=l*a.w[z];}
    std::vector<Vec2> reaction(b.size());std::vector<double> torque(b.size(),0.0);
    for(int m=0;m<nm;++m){const auto& a=markers[m];Vec2 l{in[2*m],in[2*m+1]};reaction[a.body]+=l;torque[a.body]+=cross(a.r,l);}
    // Subtract the actual impulse deposited in each fictitious interior. This
    // includes cross-body stencil overlap; independent-body force solves do not.
    for(size_t k=0;k<b.size();++k)if(!b[k].fixed){
        if(compact){for(const auto& e:interior_active[k]){Vec2 j=spread[e.first];reaction[k]-=j*e.second.area;torque[k]-=cross(e.second.first-b[k].x*e.second.area,j);}}
        else {for(const auto& e:chi[k]){Vec2 j=spread[e.first];reaction[k]-=j*e.second.area;torque[k]-=cross(e.second.first-b[k].x*e.second.area,j);}}
    }
    std::vector<double> out(2*nm);
    for(int m=0;m<nm;++m){const auto& a=markers[m];Vec2 v;for(int z=0;z<16;++z)v+=spread[compact?a.active[z]:a.node[z]]*(a.w[z]/f.rho[a.node[z]]);
        if(!b[a.body].fixed)v+=reaction[a.body]/b[a.body].mass+perp(a.r)*(torque[a.body]/b[a.body].inertia);
        out[2*m]=v.x;out[2*m+1]=v.y;
    }return out;
}
double IBM::operator_entry(const LBM& f,const std::vector<Body>& b,int row,int col) const{
    const auto& a=markers[row/2];const auto& d=markers[col/2];int c=row%2,h=col%2;double value=0;
    if(c==h)value=gram(f,a,d);
    const auto& body=b[a.body];if(body.fixed)return value;
    double s=0,tx=0,ty=0;
    for(int j=0;j<16;++j){auto q=quadrature(chi[a.body],d.node[j]);double w=d.w[j];s+=q.area*w;tx-=w*(q.first.y-body.x.y*q.area);ty+=w*(q.first.x-body.x.x*q.area);}
    double translation=((a.body==d.body)?1.0:0.0)-s;
    double rotation=(a.body==d.body?(h==0?-d.r.y:d.r.x):0.0)-(h==0?tx:ty);
    if(c==h)value+=translation/body.mass;
    value+=(c==0?-a.r.y:a.r.x)*rotation/body.inertia;
    return value;
}
void IBM::prepare_preconditioner(const LBM& f,const std::vector<Body>& b){
    int n=2*markers.size();
    if(mode==Mode::Reference){diagonal.resize(n);for(int j=0;j<n;++j)diagonal[j]=operator_entry(f,b,j,j);stats.blocks=n;return;}
    std::vector<int> group(b.size()),count(b.size(),1);std::iota(group.begin(),group.end(),0);
    auto root=[&group](int a){while(group[a]!=a)a=group[a];return a;};
    for(size_t i=0;i<b.size();++i)for(size_t j=0;j<i;++j)if(norm(b[i].x-b[j].x)-b[i].radius-b[j].radius<near_gap){int a=root(i),c=root(j);if(a!=c&&count[a]+count[c]<=max_bodies_per_block){group[a]=c;count[c]+=count[a];}}
    for(size_t i=0;i<group.size();++i)group[i]=root(i);
    bool rebuild=force_rebuild||blocks.empty()||cache_positions.size()!=b.size()||group!=cache_groups||cache_dimension!=n;
    if(!rebuild)for(size_t i=0;i<b.size();++i)if(norm(b[i].x-cache_positions[i])+b[i].radius*std::abs(b[i].angle-cache_angles[i])>cache_motion_limit)rebuild=true;
    if(rebuild){
        blocks.clear();for(size_t k=0;k<b.size();++k)if(group[k]==int(k)){
            Block block;std::vector<int> points,mobile;
            for(size_t m=0;m<markers.size();++m)if(group[markers[m].body]==int(k)){points.push_back(m);block.ids.push_back(2*m);block.ids.push_back(2*m+1);}
            for(size_t q=0;q<b.size();++q)if(group[q]==int(k)&&!b[q].fixed)mobile.push_back(q);
            const int nm=points.size(),d=2*nm,rank=3*mobile.size();if(!d)continue;
            std::vector<double> G(nm*nm),U(d*rank,0),D(rank*d,0);
            for(int i=0;i<nm;++i)for(int j=0;j<nm;++j)G[i*nm+j]=gram(f,markers[points[i]],markers[points[j]]);
            for(size_t q=0;q<mobile.size();++q){int body_id=mobile[q],base=3*q;const auto& body=b[body_id];
                for(int m=0;m<nm;++m){const auto& a=markers[points[m]];const bool own=a.body==body_id;
                    if(own){U[(2*m)*rank+base]=1/body.mass;U[(2*m+1)*rank+base+1]=1/body.mass;U[(2*m)*rank+base+2]=-a.r.y/body.inertia;U[(2*m+1)*rank+base+2]=a.r.x/body.inertia;}
                    double s=0,tx=0,ty=0;for(int j=0;j<16;++j){auto m=quadrature(chi[body_id],a.node[j]);double w=a.w[j];s+=m.area*w;tx-=w*(m.first.y-body.x.y*m.area);ty+=w*(m.first.x-body.x.x*m.area);}
                    D[base*d+2*m]=(own?1.0:0.0)-s;D[(base+1)*d+2*m+1]=(own?1.0:0.0)-s;
                    D[(base+2)*d+2*m]=(own?-a.r.y:0.0)-tx;D[(base+2)*d+2*m+1]=(own?a.r.x:0.0)-ty;
                }
            }
            block.factor.setup(G,nm,U,D,rank);blocks.push_back(std::move(block));
        }
        cache_positions.clear();cache_angles.clear();for(const auto& p:b){cache_positions.push_back(p.x);cache_angles.push_back(p.angle);}cache_groups=group;cache_dimension=n;force_rebuild=false;
    }
    stats.preconditioner_rebuilt=rebuild;stats.blocks=blocks.size();
}
std::vector<double> IBM::precondition(const std::vector<double>& in) const{
    std::vector<double> out(in.size());
    if(mode==Mode::Reference){for(size_t i=0;i<in.size();++i)out[i]=in[i]/diagonal[i];return out;}
    for(const auto& block:blocks){std::vector<double> rhs;rhs.reserve(block.ids.size());for(int id:block.ids)rhs.push_back(in[id]);block.factor.applyInPlace(rhs);for(size_t i=0;i<block.ids.size();++i)out[block.ids[i]]=rhs[i];}
    return out;
}
std::vector<double> IBM::solve(const LBM& f,const std::vector<Body>& b,const std::vector<double>& rhs){
    const int n=rhs.size();std::vector<double> x=previous_impulse.size()==rhs.size()?previous_impulse:std::vector<double>(n,0.0);
    // Both measured modes use the SAME compact current operator. Full-grid
    // apply_operator(...,false) is retained only as an independent test oracle.
    const bool compact=true;const double target=absolute_tolerance+relative_tolerance*length(rhs);
    auto residual=[&](const std::vector<double>& v){auto r=rhs;axpy(r,-1,apply_operator(f,b,v,compact));return r;};
    auto r=residual(x);double beta=length(r);int total=0;
    while(beta>target && total<max_iterations){
        int kmax=std::min({restart,n,max_iterations-total});
        std::vector<std::vector<double>> v(kmax+1,std::vector<double>(n)),z(kmax,std::vector<double>(n));
        std::vector<double> h((kmax+1)*kmax,0),cs(kmax),sn(kmax),g(kmax+1,0);g[0]=beta;
        for(int i=0;i<n;++i)v[0][i]=r[i]/beta;
        int used=0;
        for(int j=0;j<kmax;++j){
            z[j]=precondition(v[j]);auto w=apply_operator(f,b,z[j],compact);
            // Two-pass modified Gram-Schmidt prevents a false small residual.
            for(int pass=0;pass<2;++pass)for(int i=0;i<=j;++i){double p=inner(w,v[i]);h[i*kmax+j]+=p;axpy(w,-p,v[i]);}
            double hn=length(w);h[(j+1)*kmax+j]=hn;if(hn>1e-30)for(int i=0;i<n;++i)v[j+1][i]=w[i]/hn;
            for(int i=0;i<j;++i){double p=h[i*kmax+j],q=h[(i+1)*kmax+j];h[i*kmax+j]=cs[i]*p+sn[i]*q;h[(i+1)*kmax+j]=-sn[i]*p+cs[i]*q;}
            double p=h[j*kmax+j],q=h[(j+1)*kmax+j],den=std::hypot(p,q);if(den<1e-30)throw std::runtime_error("GMRES breakdown");cs[j]=p/den;sn[j]=q/den;h[j*kmax+j]=den;h[(j+1)*kmax+j]=0;
            g[j+1]=-sn[j]*g[j];g[j]*=cs[j];++total;used=j+1;
            if(std::abs(g[j+1])<=target || hn<1e-30)break;
        }
        std::vector<double> y(used);for(int i=used-1;i>=0;--i){y[i]=g[i];for(int j=i+1;j<used;++j)y[i]-=h[i*kmax+j]*y[j];y[i]/=h[i*kmax+i];}
        for(int j=0;j<used;++j)axpy(x,y[j],z[j]);
        r=residual(x);beta=length(r);
    }
    stats.iterations=total;stats.residual=beta;
    if(!std::isfinite(beta)||!std::isfinite(target)||beta>target){std::ostringstream ss;ss<<"IBM failed current-operator residual: "<<beta<<" > "<<target<<" after "<<total<<" iterations";throw std::runtime_error(ss.str());}
    if(total>restart)force_rebuild=true;
    previous_impulse=x;return x;
}
void IBM::couple(LBM& f,std::vector<Body>& b){couple_impl(f,b,false);}
void IBM::couple_prescribed(LBM& f,std::vector<Body>& b){couple_impl(f,b,true);}
void IBM::couple_impl(LBM& f,std::vector<Body>& b,bool prescribed){
    if(!initialized)throw std::runtime_error("Call IBM.initialize before advancing the fluid or bodies");
    if(restart<1||max_iterations<0||max_bodies_per_block<1||!std::isfinite(relative_tolerance)||relative_tolerance<0||!std::isfinite(absolute_tolerance)||absolute_tolerance<0||!std::isfinite(cache_motion_limit)||cache_motion_limit<=0||!std::isfinite(near_gap)||near_gap<0)throw std::invalid_argument("Invalid IBM solve or cache settings");
    stats=IBMStats{};auto start=Clock::now();build_geometry(f,b);if(old_interior.size()!=b.size())throw std::runtime_error("Particle insertion/removal is not implemented");
    if(prescribed!=last_prescribed){blocks.clear();previous_impulse.clear();force_rebuild=true;last_prescribed=prescribed;}
    // Keep the physical bodies unchanged. The prescribed-velocity operator
    // has no rigid-body acceleration term, so use a constrained copy only
    // for operator/preconditioner construction and the Krylov solve.
    std::vector<Body> constrained_bodies;
    const std::vector<Body>* operator_bodies=&b;
    if(prescribed){constrained_bodies=b;for(auto& p:constrained_bodies)p.fixed=true;operator_bodies=&constrained_bodies;}
    auto pred=interior_momentum(f,b);std::vector<Vec2> free_v(b.size());std::vector<double> free_w(b.size());
    for(size_t k=0;k<b.size();++k){
        if(prescribed){free_v[k]=b[k].v;free_w[k]=b[k].omega;}
        else if(!b[k].fixed){Vec2 dp=pred[k].p-old_interior[k].p;free_v[k]=b[k].v+dp/b[k].mass;free_w[k]=b[k].omega+(pred[k].angular-old_interior[k].angular-cross(b[k].x,dp))/b[k].inertia;}
    }
    std::vector<double> rhs(2*markers.size());
    for(size_t m=0;m<markers.size();++m){const auto& a=markers[m];Vec2 u;for(int z=0;z<16;++z)u+=f.u[a.node[z]]*a.w[z];Vec2 goal=free_v[a.body]+perp(a.r)*free_w[a.body];rhs[2*m]=goal.x-u.x;rhs[2*m+1]=goal.y-u.y;}
    prepare_preconditioner(f,*operator_bodies);stats.markers=markers.size();stats.active_nodes=active_nodes.size();stats.setup_seconds=seconds(start);
    start=Clock::now();auto lambda=solve(f,*operator_bodies,rhs);stats.solve_seconds=seconds(start);
    std::vector<Vec2> spread(compact_commit?active_nodes.size():static_cast<size_t>(f.n)),body_impulse(b.size());std::vector<double> body_global_torque(b.size(),0);
    Vec2 grid_impulse;double grid_torque=0;
    for(size_t m=0;m<markers.size();++m){const auto& a=markers[m];Vec2 l{lambda[2*m],lambda[2*m+1]};body_impulse[a.body]+=l;body_global_torque[a.body]+=cross(a.x,l);for(int z=0;z<16;++z)spread[compact_commit?a.active[z]:a.node[z]]+=l*a.w[z];}
    for(size_t k=0;k<spread.size();++k){int i=compact_commit?active_nodes[k]:static_cast<int>(k);grid_impulse+=spread[k];grid_torque+=cross({double(i%f.nx),double(i/f.nx)},spread[k]);}
    if(compact_commit) f.apply_indexed_impulse(active_nodes,spread); else f.apply_impulse(spread);
    auto current=interior_momentum(f,b);
    Vec2 marker_total;double marker_torque=0;
    hydrodynamic_impulse.resize(b.size());
    for(size_t k=0;k<b.size();++k){marker_total+=body_impulse[k];marker_torque+=body_global_torque[k];Vec2 dp=current[k].p-old_interior[k].p;
        auto& impulse=hydrodynamic_impulse[k];impulse.linear=dp-body_impulse[k];impulse.angular=current[k].angular-old_interior[k].angular-body_global_torque[k];
        if(!prescribed&&!b[k].fixed){b[k].v+=impulse.linear/b[k].mass;b[k].omega+=(impulse.angular-cross(b[k].x,impulse.linear))/b[k].inertia;}
    }
    stats.impulse_balance=norm(grid_impulse-marker_total);stats.angular_balance=std::abs(grid_torque-marker_torque);
    for(const auto& a:markers){Vec2 u;for(int z=0;z<16;++z)u+=f.u[a.node[z]]*a.w[z];Vec2 rigid=(!prescribed&&b[a.body].fixed)?Vec2{}:b[a.body].v+perp(a.r)*b[a.body].omega;stats.max_slip=std::max(stats.max_slip,norm(u-rigid));}
    old_interior=current;
}
}
