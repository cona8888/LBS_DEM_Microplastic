#pragma once

#include "common.hpp"

#include <array>
#include <vector>

namespace ibdem {

// Periodic, isothermal D2Q9 in lattice units dx = dt = rho_ref = 1.
// The two population buffers use direction-major structure-of-arrays storage.
// There is no half-force velocity convention: u is the population momentum / rho.
class LBM {
public:
    static constexpr int q_count = 9;
    inline static constexpr std::array<int, q_count> cx{{0, 1, 0, -1, 0, 1, -1, -1, 1}};
    inline static constexpr std::array<int, q_count> cy{{0, 0, 1, 0, -1, 1, 1, -1, -1}};
    inline static constexpr std::array<int, q_count> opposite{{0, 3, 4, 1, 2, 7, 8, 5, 6}};
    inline static constexpr std::array<double, q_count> weight{{
        4.0/9.0, 1.0/9.0, 1.0/9.0, 1.0/9.0, 1.0/9.0,
        1.0/36.0, 1.0/36.0, 1.0/36.0, 1.0/36.0
    }};

    const int nx;
    const int ny;
    const int n;
    const double tau_plus;
    const double magic;
    const double tau_minus;

    std::vector<double> rho;
    std::vector<Vec2> u;
    std::vector<double> f; // f[q*n + i]; call macros() after any external edit.

    explicit LBM(int nx_, int ny_, double tau_plus_ = 0.8,
                 double magic_ = 3.0/16.0);

    void initialize(Vec2 velocity = {}, double density = 1.0);
    void initialize(const std::vector<Vec2>& velocities, double density = 1.0);

    // Refresh density and raw momentum velocity from f.
    void macros();

    // Unforced TRT collision followed by periodic streaming and macros().
    // (tau_plus - 1/2)(tau_minus - 1/2) = magic.
    void collide_stream();

    // Global-origin angular-momentum change caused by periodic population
    // wraps in the preceding collide_stream(). Computed from current f:
    // call immediately after streaming, BEFORE any IBM/other population kick.
    // Both coordinate shifts contribute when a diagonal wraps at a corner.
    double periodic_angular_flux() const;

    // Apply a full momentum-density impulse at each Eulerian cell:
    // f += feq(rho, u + impulse/rho) - feq(rho, u).
    // This conserves mass and adds precisely the supplied momentum, up to
    // floating-point roundoff. It is a full equilibrium difference, including
    // the quadratic velocity terms, and is NOT a Guo half-force update.
    void apply_impulse(const std::vector<Vec2>& impulse);

    // Indexed equivalent of a zero-filled dense impulse. Prevalidate all touched nodes
    // before changing state. nodes must be sorted, unique and valid.
    void apply_indexed_impulse(const std::vector<int>& nodes, const std::vector<Vec2>& impulses);

    double viscosity() const noexcept { return (tau_plus - 0.5)/3.0; }
    static std::array<double, q_count> equilibrium(double density, Vec2 velocity);

private:
    std::vector<double> next_;
    double omega_plus_;
    double omega_minus_;
};

} // namespace ibdem
