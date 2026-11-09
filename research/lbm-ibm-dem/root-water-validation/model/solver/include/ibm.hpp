#pragma once
#include "common.hpp"
#include "lbm.hpp"
#include "block_preconditioner.hpp"
#include "disk_quadrature.hpp"
#include <array>
#include <unordered_map>
#include <string>

namespace ibdem {
// A full-step impulse formulation: lambda stores INTEGRATED marker impulses.
// It is not a force density and does not use a Guo half-force velocity.
struct Marker {
    int body=0;
    Vec2 x, r;
    std::array<int,16> node{}, active{};
    std::array<double,16> w{};
};
struct InteriorMomentum { Vec2 p; double angular=0.0; };
// Physical hydrodynamic impulse ON a body during the last accepted coupling
// interval, including the change of fictitious interior-fluid momentum.
// angular is about the fixed global origin, not the body's moving center.
// For a fixed/prescribed body, its actuator/support supplies the opposite
// impulse (plus the opposite of any separately applied contact/body loads).
struct HydrodynamicImpulse { Vec2 linear; double angular=0.0; };
struct IBMStats {
    int iterations=0, markers=0, active_nodes=0, blocks=0;
    bool preconditioner_rebuilt=false;
    double setup_seconds=0.0, solve_seconds=0.0, residual=0.0;
    double max_slip=0.0, impulse_balance=0.0, angular_balance=0.0;
};
class IBM {
public:
    enum class Mode { Reference, CachedBlocks };
    Mode mode;
    double relative_tolerance=1e-10, absolute_tolerance=1e-13;
    double marker_spacing=2.0, cache_motion_limit=0.15;
    // Optional numerical inward displacement of constraint markers, in
    // lattice units. Physical Body::radius, interior integration, mass/inertia
    // and contact geometry are unchanged. Zero preserves the original method;
    // any nonzero choice requires hydrodynamic resolution/calibration evidence.
    double marker_retraction=0.0;
    // Same impulse, visited only on the sorted unique support of all markers.
    bool compact_commit=false; // dense is retained as the numerical reference
    int max_iterations=800, restart=60, max_bodies_per_block=2;
    double near_gap=3.0;
    std::vector<Marker> markers;
    std::vector<int> active_nodes;
    std::vector<InteriorMomentum> old_interior;
    std::vector<HydrodynamicImpulse> hydrodynamic_impulse;
    IBMStats stats;
    explicit IBM(Mode m=Mode::CachedBlocks):mode(m){}
    void initialize(const LBM& fluid,const std::vector<Body>& bodies);
    // Must be called after the fluid predictor and optional DEM advancement.
    // Body positions are held fixed during this implicit velocity/impulse solve.
    void couple(LBM& fluid,std::vector<Body>& bodies);
    // Calibration mode: impose the supplied v/omega of EVERY body, including
    // bodies marked fixed, at the current geometry. Body state is not changed.
    // Only the constraint operator treats the bodies as infinitely massive;
    // physical radius/mass/inertia and interior accounting are retained.
    void couple_prescribed(LBM& fluid,std::vector<Body>& bodies);
    // Public diagnostic operators for independently checking the discretization.
    void build_geometry(const LBM& fluid,const std::vector<Body>& bodies);
    std::vector<double> apply_operator(const LBM& fluid,const std::vector<Body>& bodies,
                                       const std::vector<double>& impulse,bool compact) const;
    double operator_entry(const LBM&,const std::vector<Body>&,int row,int col) const;
    std::vector<InteriorMomentum> interior_momentum(const LBM&,const std::vector<Body>&) const;
    static double kernel(double x);
    static double disk_cell_area(Vec2 centre,double radius,int x,int y);
private:
    struct GeometryCache { Vec2 x; double radius=-1,angle=0,spacing=0,retraction=0; std::vector<Marker> points; };
    std::vector<GeometryCache> geometry_cache;
    int geometry_nx=0,geometry_ny=0;
    struct Block { std::vector<int> ids; StructuredBlockPreconditioner factor; };
    std::vector<std::unordered_map<int,DiskCellMoments>> chi;
    std::vector<std::vector<std::pair<int,DiskCellMoments>>> interior_active;
    std::vector<Block> blocks;
    std::vector<double> diagonal, previous_impulse;
    std::vector<Vec2> cache_positions;
    std::vector<double> cache_angles;
    std::vector<int> cache_groups;
    int cache_dimension=0;
    bool initialized=false, force_rebuild=false;
    bool last_prescribed=false;
    void couple_impl(LBM&,std::vector<Body>&,bool prescribed);
    void prepare_preconditioner(const LBM&,const std::vector<Body>&);
    std::vector<double> precondition(const std::vector<double>&) const;
    std::vector<double> solve(const LBM&,const std::vector<Body>&,const std::vector<double>& rhs);
};
}
