#pragma once

#include "common.hpp"
#include <cstddef>
#include <cstdint>
#include <unordered_map>

namespace ibdem {

// A deliberately explicit 2-D compliant contact model, per unit out-of-plane
// depth. It is a disk model, not the three-dimensional Hertz/Mindlin law.
//
// n points from the lower-ID body to the higher-ID body; t=perp(n).
// R_a and R_b below are contactRadius() = radius+contact_offset.
// delta = R_a+R_b-|x_b-x_a|, vn=(v_a-v_b).n (positive on approach).
// The smooth hydrodynamic radius, physical mass/inertia and supplied stiffness
// are unaffected by the offset. A wet integrator must separately prevent core
// overlap: the core gap is offset_a+offset_b-delta, not -delta.
// Fn=max(0,kn*delta+cn*vn), and the force on a is -Fn*n+Ft*t.
// Ft=clamp(-kt*xi-ct*vt,-mu*Fn,mu*Fn). The tangential spring/dashpot is
// a Kelvin-Voigt element in series with a Coulomb slider: in sticking,
// xi_dot=vt; in sliding, kt*xi+ct*xi_dot=mu*Fn*sign(plastic slip).
// Its discrete return map uses the ELASTIC slip rate in the dashpot and
// does not create a large artificial spring to cancel a capped dashpot.
// With ct=0 this is the usual capped elastic history; with kt=0 it is
// capped viscous friction. The finite-ct sliding return map is implicit Euler.
// The scalar xi is expressed in the rotating contact tangent: a rotation of
// the contact frame does not spuriously shorten an existing spring.
//
// Forces act at one common contact point, with lever lengths
// la=(r+Ra-Rb)/2 and lb=r-la. This makes total spin+orbital torque cancel
// exactly, including finite overlaps. Fixed bodies accumulate their reaction
// forces/torques but have zero contact-point velocity and are never advanced.
// No periodic boundaries, wall planes, lubrication, adhesion or rolling law.
class DEM {
public:
    double kn=1.0e4, kt=2.0e3, cn=0.0, ct=0.0, mu=0.4;

    struct Diagnostics {
        std::size_t contact_count=0; // Geometrically overlapping/touching pairs.
        std::size_t force_count=0;   // Pairs carrying a positive normal force.
        double max_overlap=0.0;
        double max_friction_ratio=0.0; // |Ft|/Fn, compared with mu.
        double elastic_energy=0.0;  // Nominal normal + stored tangential energy.
    } stats; // Snapshot of the most recent evaluation, not a temporal maximum.
    std::size_t force_evaluations=0;

    // Clears Body::force/torque and fills CONTACT forces only. dt>0 commits
    // exactly one explicit slip-history increment; dt=0 only refreshes force
    // and prunes separated/unloaded histories. Repeated dt=0 queries never
    // accumulate slip. Copy DEM when evaluating trial states needing rollback.
    void evaluate(std::vector<Body>& bodies, double dt=0.0);

    // Advances the physical masses/stiffnesses without collision-time scaling.
    // Uses kick-drift-kick substeps, midpoint slip integration and an endpoint
    // velocity prediction for velocity-dependent forces. Smooth conservative
    // forces use ordinary velocity Verlet. Contact creation/sliding/release
    // require a timestep convergence study even when this method is stable.
    // external and externalTorque are constant FORCES/TORQUES over dt, indexed
    // like bodies; an empty vector means zero. Body::force remains contact-only.
    void advance(std::vector<Body>& bodies, double dt, int substeps=1,
                 const std::vector<Vec2>& external={},
                 const std::vector<double>& externalTorque={});

    void clearHistory() { history_.clear(); }
    std::size_t historySize() const { return history_.size(); }
    double tangentialHistory(int id_a, int id_b) const;

private:
    struct Pair {
        int a, b;
        bool operator==(const Pair& p) const { return a==p.a && b==p.b; }
    };
    struct PairHash {
        std::size_t operator()(const Pair& p) const {
            const auto a=static_cast<std::uint32_t>(p.a);
            const auto b=static_cast<std::uint32_t>(p.b);
            return std::hash<std::uint64_t>{}((std::uint64_t(a)<<32)|b);
        }
    };
    std::unordered_map<Pair,double,PairHash> history_;
    static Pair key(int a, int b);
    void validate(const std::vector<Body>& bodies) const;
    void advanceHistory(const std::vector<Body>& old_bodies,
                        const std::vector<Body>& predicted_bodies, double dt);
};

} // namespace ibdem
