#include "ibm.hpp"
#include "dem.hpp"
#include <iostream>
#include <fstream>
#include <iomanip>
#include <chrono>
#include <string>
#include <algorithm>
#ifdef _OPENMP
#include <omp.h>
#endif

using namespace ibdem;
namespace {
using Clock=std::chrono::steady_clock;
double elapsed(Clock::time_point start){return std::chrono::duration<double>(Clock::now()-start).count();}
double mass(const LBM& fluid){double value=0;for(double x:fluid.rho)value+=x;return value;}
std::vector<Body> scenario(const std::string& name,int& nx,int& ny){
    std::vector<Body> b;
    if(name=="sparse"){
        nx=128;ny=96;
        for(int y=0;y<2;++y)for(int x=0;x<3;++x){int id=y*3+x;b.push_back(disk(id,{35.2+22*x,36.3+22*y},5.0,1.2,id%2==1));}
    }else if(name=="near"){
        nx=80;ny=64;
        for(int y=0;y<3;++y)for(int x=0;x<4;++x){int id=y*4+x;b.push_back(disk(id,{21.2+11.5*x,20.3+11.5*y},5.0,1.2,id%3==1));}
    }else if(name=="recoil"){
        nx=64;ny=48;b.push_back(disk(0,{25.3,24.7},6,0.8));b[0].v={.008,-.003};b[0].omega=.0002;
    }else if(name=="porous"){
        nx=128;ny=96;
        b.push_back(disk(0,{19.3,47.7},3.5,1.2));
        for(int y=0;y<4;++y)for(int x=0;x<5;++x)b.push_back(disk(1+y*5+x,{35.2+16*x,23.3+16*y},5.0,2.65,true));
    }else throw std::invalid_argument("Unknown case: choose sparse, near, porous, or recoil");
    return b;
}
}
int main(int argc,char** argv){
 try{
    std::string mode="fast",name="near",output,trajectory;
    int steps=100,substeps=4,block_size=1;
    for(int i=1;i<argc;++i){std::string a=argv[i];
        if(a=="--help"){std::cout<<"ibdem --mode ref|fast --case sparse|near|porous|recoil --steps N [--block-size 1|2] [--state FILE] [--trajectory FILE]\n"
            <<"2D periodic research prototype. Wet overlaps are rejected. No lubrication, 3D, AMR, or GPU backend.\n";return 0;}
        if(i+1>=argc)throw std::invalid_argument("Option requires value: "+a);
        std::string value=argv[++i];
        if(a=="--mode")mode=value;else if(a=="--case")name=value;else if(a=="--steps")steps=std::stoi(value);else if(a=="--substeps")substeps=std::stoi(value);else if(a=="--block-size")block_size=std::stoi(value);else if(a=="--state")output=value;else if(a=="--trajectory")trajectory=value;else throw std::invalid_argument("Unknown option: "+a);
    }
    if(mode!="ref"&&mode!="fast")throw std::invalid_argument("Mode must be ref or fast");
    if(steps<1||substeps<1)throw std::invalid_argument("Positive steps and substeps required");
    if(block_size<1||block_size>2)throw std::invalid_argument("Demonstrator block size must be 1 or 2");
    auto total_start=Clock::now();int nx=0,ny=0;auto bodies=scenario(name,nx,ny);LBM fluid(nx,ny);if(name!="recoil")fluid.initialize({.004,0});
    IBM ib(mode=="ref"?IBM::Mode::Reference:IBM::Mode::CachedBlocks);ib.relative_tolerance=1e-10;ib.max_bodies_per_block=block_size;ib.initialize(fluid,bodies);
    DEM dem;dem.kn=2.0;dem.kt=.8;dem.cn=.01;dem.ct=.005;dem.mu=.4;
    const double initial_mass=mass(fluid);int iterations=0,rebuilds=0,max_iterations=0,max_contacts=0;double setup_seconds=0,solve_seconds=0,lbm_seconds=0,dem_seconds=0,coupling_seconds=0,max_slip=0,max_residual=0,max_impulse_error=0,max_angular_error=0,max_speed=0,min_gap=1e100;
    std::ofstream trajectory_file;if(!trajectory.empty()){trajectory_file.open(trajectory);if(!trajectory_file)throw std::runtime_error("Cannot open trajectory file");trajectory_file<<"step,id,x,y,vx,vy,angle,omega\n";}
    for(int step=0;step<steps;++step){
        auto t=Clock::now();dem.advance(bodies,1.0,substeps);dem_seconds+=elapsed(t);max_contacts=std::max(max_contacts,static_cast<int>(dem.stats.contact_count));
        t=Clock::now();fluid.collide_stream();lbm_seconds+=elapsed(t);
        t=Clock::now();ib.couple(fluid,bodies);coupling_seconds+=elapsed(t);setup_seconds+=ib.stats.setup_seconds;solve_seconds+=ib.stats.solve_seconds;
        iterations+=ib.stats.iterations;max_iterations=std::max(max_iterations,ib.stats.iterations);rebuilds+=ib.stats.preconditioner_rebuilt;max_slip=std::max(max_slip,ib.stats.max_slip);max_residual=std::max(max_residual,ib.stats.residual);max_impulse_error=std::max(max_impulse_error,ib.stats.impulse_balance);max_angular_error=std::max(max_angular_error,ib.stats.angular_balance);
        for(auto v:fluid.u)max_speed=std::max(max_speed,norm(v));
        for(size_t i=0;i<bodies.size();++i){for(size_t j=0;j<i;++j)min_gap=std::min(min_gap,norm(bodies[i].x-bodies[j].x)-bodies[i].radius-bodies[j].radius);if(trajectory_file)trajectory_file<<std::setprecision(17)<<step+1<<','<<bodies[i].id<<','<<bodies[i].x.x<<','<<bodies[i].x.y<<','<<bodies[i].v.x<<','<<bodies[i].v.y<<','<<bodies[i].angle<<','<<bodies[i].omega<<'\n';}
    }
    double total_seconds=elapsed(total_start);
    if(!output.empty()){std::ofstream file(output,std::ios::binary);if(!file)throw std::runtime_error("Cannot open state file");file.write(reinterpret_cast<const char*>(fluid.f.data()),fluid.f.size()*sizeof(double));for(const auto& b:bodies){double state[]={b.x.x,b.x.y,b.v.x,b.v.y,b.angle,b.omega};file.write(reinterpret_cast<const char*>(state),sizeof(state));}}
    int threads=1;
#ifdef _OPENMP
    threads=omp_get_max_threads();
#endif
    std::cout<<std::setprecision(17)<<"{\"case\":\""<<name<<"\",\"mode\":\""<<mode<<"\",\"steps\":"<<steps<<",\"nx\":"<<nx<<",\"ny\":"<<ny<<",\"bodies\":"<<bodies.size()<<",\"markers\":"<<ib.stats.markers<<",\"threads\":"<<threads
    <<",\"total_seconds\":"<<total_seconds<<",\"fluid_seconds\":"<<lbm_seconds<<",\"dem_seconds\":"<<dem_seconds<<",\"coupling_seconds\":"<<coupling_seconds<<",\"setup_seconds\":"<<setup_seconds<<",\"solve_seconds\":"<<solve_seconds<<",\"iterations_total\":"<<iterations<<",\"iterations_max\":"<<max_iterations<<",\"preconditioner_rebuilds\":"<<rebuilds<<",\"max_contacts\":"<<max_contacts
    <<",\"max_slip\":"<<max_slip<<",\"max_residual\":"<<max_residual<<",\"max_spreading_impulse_error\":"<<max_impulse_error<<",\"max_spreading_angular_error\":"<<max_angular_error<<",\"relative_lattice_mass_drift\":"<<std::abs(mass(fluid)-initial_mass)/initial_mass<<",\"peak_fluid_speed\":"<<max_speed<<",\"min_gap\":"<<(min_gap>1e90?-1:min_gap)<<",\"relative_tolerance\":"<<ib.relative_tolerance<<",\"absolute_tolerance\":"<<ib.absolute_tolerance<<",\"dem_substeps\":"<<substeps<<",\"max_bodies_per_block\":"<<block_size<<"}\n";
    return 0;
 }catch(const std::exception& e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}
}
