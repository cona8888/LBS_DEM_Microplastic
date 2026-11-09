#include "film_port.hpp"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

// Stationary two-port benchmark; one row per positive gap argument.
int main(int argc,char** argv) {
    try {
        std::string path;std::vector<double> gaps;
        for(int i=1;i<argc;++i) {
            const std::string arg=argv[i];
            if(arg=="--help") {
                std::cout<<"film_conductance [--output FILE] [h/a ...]\n"
                         <<"Defaults: 0.04 0.01 0.0025 0.000625; a=b=1, mu=1, "
                           "pressure_left=1, pressure_right=0, L=2*sqrt(h).\n";
                return 0;
            }
            if(arg=="--output") {
                if(++i>=argc||!path.empty())throw std::invalid_argument("Supply one output filename");
                path=argv[i];continue;
            }
            std::size_t used=0;double h=std::stod(arg,&used);
            if(used!=arg.size()||!std::isfinite(h)||!(h>0))
                throw std::invalid_argument("All h/a values must be finite and positive");
            gaps.push_back(h);
        }
        if(gaps.empty())gaps={0.04,0.01,0.0025,0.000625};
        std::ofstream file;
        if(!path.empty()){file.open(path);if(!file)throw std::runtime_error("Cannot create "+path);}
        std::ostream& out=path.empty()?std::cout:file;
        out<<std::setprecision(17)<<"h_over_a,radius_a,radius_b,effective_radius,half_length,viscosity,"
             "pressure_left,pressure_right,flux_center,flux_out_left,flux_out_right,conductance,"
             "mu_G_over_a2,port_power,dissipation,volume_residual,power_residual\n";
        for(double h:gaps) {
            ibdem::FilmPortInput v;
            v.radius_a=1;v.radius_b=1;v.h=h;v.half_length=2*std::sqrt(h);
            v.viscosity=1;v.pressure_left=1;v.pressure_right=0;
            const auto f=ibdem::ReynoldsFilmPort(v).evaluate();
            out<<h<<','<<v.radius_a<<','<<v.radius_b<<','<<f.effective_radius<<','
               <<v.half_length<<','<<v.viscosity<<','<<v.pressure_left<<','<<v.pressure_right<<','
               <<f.center_flux<<','<<f.outward_left<<','<<f.outward_right<<','<<f.conductance<<','
               <<v.viscosity*f.conductance/(v.radius_a*v.radius_a)<<','<<f.port_power<<','
               <<f.dissipation<<','<<f.volume_residual<<','<<f.power_residual<<'\n';
        }
        if(!out)throw std::runtime_error("Failed to write the complete conductance table");
        return 0;
    } catch(const std::exception& e) {std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}
}
