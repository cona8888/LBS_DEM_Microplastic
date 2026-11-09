#pragma once

#include "common.hpp"
#include <array>
#include <cstddef>
#include <vector>

namespace ibdem {

// Frozen-geometry, two-dimensional cylinder near-field resistance correction.
// Forces/torques are per unit out-of-plane length. viscosity is DYNAMIC mu.
// It is not a calibrated subtraction of this code's measured IBM resistance.
// Cutoffs and positive-gap regularization are explicit model parameters.
class NearField {
public:
    double viscosity=1.0;
    double normal_cutoff=1.0;
    double tangential_cutoff=1.0;
    double min_gap=1.0e-3;
    bool enabled=true;

    struct PairResistance {
        Vec2 n,t;
        double gap=0.0, effective_gap=0.0, effective_radius=0.0;
        double Rn=0.0, Ct=0.0;
        double la=0.0, lb=0.0, beta=0.0;
        // Local DOFs: [Va.x,Va.y,wa,Vb.x,Vb.y,wb].
        // Rows give vn, sliding s, and pumping/rotation p.
        std::array<std::array<double,6>,3> modes{};
    };

    struct PairEntry {
        std::size_t a=0,b=0; // Indices in the supplied body vector.
        PairResistance resistance;
    };

    struct BodyImpulse {
        Vec2 linear;
        double angular=0.0;        // About this body's center.
        double angular_global=0.0; // cross(x,linear)+angular at frozen x.
    };

    struct Diagnostics {
        std::size_t active_pairs=0, active_modes=0, mobile_bodies=0, solve_dofs=0;
        double minimum_gap=0.0; // Among active pairs; 0 means no active pairs.
        double kinetic_before=0.0, kinetic_after=0.0;
        double physical_dissipation=0.0;
        double numerical_dissipation=0.0;
        double energy_residual=0.0;
        double linear_balance=0.0, angular_balance=0.0;
        double solve_residual=0.0; // Scaled infinity norm in mass-whitened units.
    } stats;

    std::vector<PairEntry> pair_table;
    std::vector<BodyImpulse> impulse; // ALL bodies, including fixed reactions.

    // Requires positive smooth-core gap. min_gap regularizes a positive gap;
    // it does not permit overlapping hydrodynamic cores. Positive cutoffs must
    // exceed min_gap; cutoff=0 explicitly disables that resistance component.
    PairResistance pair_resistance(const Body& a,const Body& b) const;

    // Solve M(U+ - U*) = -dt R U+ on mobile DOFs, with stationary fixed bodies.
    // R=sum C^T diag(Rn,Ct,Ct) C is symmetric positive semidefinite.
    // Uses dense mass-whitened Cholesky for the small research-prototype system.
    // Changes only moving-body v/omega; no position, mass, inertia, contact
    // history or Body::force/torque changes. Does not spread a second force to
    // the fluid grid. stats/impulse/pair_table are reset for each call.
    //
    // Backward Euler is unconditionally dissipative for frozen geometry and
    // first order in time. Two half calls around DEM do not make it second order.
    void apply(std::vector<Body>& bodies,double dt);

private:
    void validateSettings() const;
};

} // namespace ibdem
