#pragma once
#include "dem.hpp"
#include "near_field.hpp"
#include <algorithm>
#include <limits>

namespace ibdem {
struct WetParticleStats {
    std::size_t peak_contacts=0;
    double max_overlap=0, min_core_gap=std::numeric_limits<double>::infinity();
    double near_physical_dissipation=0, near_numerical_dissipation=0;
    double near_max_energy_residual=0, near_max_solve_residual=0;
    std::vector<Vec2> near_impulse;
    std::vector<double> near_angular_global;
};

// Particle subcycling only. The fluid predictor and IBM exchange remain once
// per fluid step. Two backward-Euler resistance half steps do not establish
// second order of either this split or the complete fluid-particle method.
inline WetParticleStats advance_wet_particles(DEM& dem, NearField& near,
        std::vector<Body>& bodies, double dt, int substeps) {
    if (!(dt>0) || !std::isfinite(dt) || substeps<1)
        throw std::invalid_argument("Wet particle advancement requires dt>0 and substeps>=1");
    WetParticleStats result;
    result.near_impulse.resize(bodies.size());
    result.near_angular_global.resize(bodies.size());
    auto check_gap=[&]() {
        for(std::size_t i=0;i<bodies.size();++i) for(std::size_t j=0;j<i;++j) {
            const double h=norm(bodies[i].x-bodies[j].x)-bodies[i].radius-bodies[j].radius;
            result.min_core_gap=std::min(result.min_core_gap,h);
            if(!(h>0) || !std::isfinite(h))
                throw std::runtime_error("Smooth hydrodynamic cores touched/overlapped: the declared asperity envelope was overcompressed. No radius or stiffness adjustment is permitted.");
        }
    };
    auto resist=[&](double h) {
        if(!near.enabled) return;
        near.apply(bodies,h);
        result.near_physical_dissipation+=near.stats.physical_dissipation;
        result.near_numerical_dissipation+=near.stats.numerical_dissipation;
        result.near_max_energy_residual=std::max(result.near_max_energy_residual,std::abs(near.stats.energy_residual));
        result.near_max_solve_residual=std::max(result.near_max_solve_residual,near.stats.solve_residual);
        for(std::size_t i=0;i<bodies.size();++i) {
            result.near_impulse[i]+=near.impulse[i].linear;
            result.near_angular_global[i]+=near.impulse[i].angular_global;
        }
    };
    check_gap();
    const double h=dt/substeps;
    for(int k=0;k<substeps;++k) {
        resist(0.5*h);
        dem.advance(bodies,h,1);
        check_gap();
        result.peak_contacts=std::max(result.peak_contacts,dem.stats.contact_count);
        result.max_overlap=std::max(result.max_overlap,dem.stats.max_overlap);
        resist(0.5*h);
    }
    return result;
}
}
