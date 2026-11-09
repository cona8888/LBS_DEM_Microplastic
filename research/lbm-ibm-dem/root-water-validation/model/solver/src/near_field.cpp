#include "near_field.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace ibdem {
namespace {

bool finite(Vec2 v) { return std::isfinite(v.x) && std::isfinite(v.y); }

void validateBody(const Body& b) {
    if (!(b.radius>0) || !std::isfinite(b.radius) || !finite(b.x) ||
        !finite(b.v) || !std::isfinite(b.omega))
        throw std::invalid_argument("NearField requires finite body geometry and velocities");
    if (!(b.contact_offset>=0) || !std::isfinite(b.contact_offset) ||
        !std::isfinite(b.contactRadius()))
        throw std::invalid_argument("NearField requires finite nonnegative contact offsets");
    if (!b.fixed && (!(b.mass>0) || !(b.inertia>0) ||
                     !std::isfinite(b.mass) || !std::isfinite(b.inertia)))
        throw std::invalid_argument("NearField moving bodies need positive finite mass and inertia");
}

std::array<double,6> pairVelocity(const Body& a,const Body& b) {
    return {a.fixed?0.0:a.v.x,a.fixed?0.0:a.v.y,a.fixed?0.0:a.omega,
            b.fixed?0.0:b.v.x,b.fixed?0.0:b.v.y,b.fixed?0.0:b.omega};
}

double kinetic(const std::vector<Body>& bodies) {
    double e=0;
    for (const Body& b:bodies) if (!b.fixed)
        e+=0.5*b.mass*dot(b.v,b.v)+0.5*b.inertia*b.omega*b.omega;
    if (!std::isfinite(e)) throw std::runtime_error("NearField nonfinite kinetic energy");
    return e;
}

double dot6(const std::array<double,6>& a,const std::array<double,6>& b) {
    double s=0;
    for (int i=0;i<6;++i) s+=a[i]*b[i];
    return s;
}

void choleskySolve(std::vector<double>& a,std::vector<double>& rhs) {
    const std::size_t n=rhs.size();
    for (std::size_t i=0;i<n;++i) for (std::size_t j=0;j<=i;++j) {
        double value=a[i*n+j];
        for (std::size_t k=0;k<j;++k) value-=a[i*n+k]*a[j*n+k];
        if (!std::isfinite(value))
            throw std::runtime_error("NearField nonfinite SPD factorization; inspect resistance scale");
        if (i==j) {
            if (!(value>0))
                throw std::runtime_error("NearField lost positive definiteness numerically; reduce timestep/resistance condition number");
            a[i*n+j]=std::sqrt(value);
        } else a[i*n+j]=value/a[j*n+j];
    }
    for (std::size_t i=0;i<n;++i) {
        for (std::size_t j=0;j<i;++j) rhs[i]-=a[i*n+j]*rhs[j];
        rhs[i]/=a[i*n+i];
    }
    for (std::size_t i=n;i-- >0;) {
        for (std::size_t j=i+1;j<n;++j) rhs[i]-=a[j*n+i]*rhs[j];
        rhs[i]/=a[i*n+i];
        if (!std::isfinite(rhs[i])) throw std::runtime_error("NearField nonfinite implicit velocity");
    }
}

} // namespace

void NearField::validateSettings() const {
    if (!(viscosity>=0) || !std::isfinite(viscosity) ||
        !(min_gap>0) || !std::isfinite(min_gap))
        throw std::invalid_argument("NearField needs finite viscosity>=0 and min_gap>0");
    for (double cutoff : {normal_cutoff,tangential_cutoff}) {
        if (!(cutoff>=0) || !std::isfinite(cutoff) || (cutoff>0 && !(cutoff>min_gap)))
            throw std::invalid_argument("NearField cutoff must be zero or finite and greater than min_gap");
    }
}

NearField::PairResistance NearField::pair_resistance(const Body& a,const Body& b) const {
    validateSettings();
    validateBody(a);
    validateBody(b);
    PairResistance p;
    const Vec2 dx=b.x-a.x;
    const double distance=norm(dx);
    if (!std::isfinite(distance) || !(distance>0))
        throw std::invalid_argument("NearField needs distinct finite particle centers");
    p.gap=distance-a.radius-b.radius;
    if (!(p.gap>0))
        throw std::runtime_error("NearField hydrodynamic cores overlap/touch; contact offsets or physical compression are incompatible");
    p.effective_gap=std::max(p.gap,min_gap);
    p.n=dx/distance;
    p.t=perp(p.n);
    const double small=std::min(a.radius,b.radius),large=std::max(a.radius,b.radius);
    p.effective_radius=small/(1+small/large);

    // Original leading-order lubrication uses the surface radii as arms. The
    // common mid-gap arms below alter it by relative O(h/R), while enforcing
    // exact pair angular balance and the common rigid-rotation null mode at
    // finite h. This is a conservative completion, not exact finite-gap flow.
    p.la=a.radius+0.5*p.gap;
    p.lb=distance-p.la;
    p.beta=(p.la-p.lb)/distance;
    p.modes[0]={p.n.x,p.n.y,0,-p.n.x,-p.n.y,0};
    p.modes[1]={p.t.x,p.t.y,p.la,-p.t.x,-p.t.y,p.lb};
    p.modes[2]={p.beta*p.t.x,p.beta*p.t.y,p.la,
                -p.beta*p.t.x,-p.beta*p.t.y,-p.lb};

    // Coefficient subtraction uses the SAME current modes C(h), preserving
    // PSD. Subtracting complete matrices C(hc)^T K(hc) C(hc) would not do so.
    if (enabled && viscosity>0) {
        if (normal_cutoff>0 && p.gap<normal_cutoff) {
            const double subtraction=-std::expm1(1.5*std::log(p.effective_gap/normal_cutoff));
            p.Rn=3*pi*std::sqrt(2.0)*viscosity*
                std::pow(p.effective_radius/p.effective_gap,1.5)*subtraction;
        }
        if (tangential_cutoff>0 && p.gap<tangential_cutoff) {
            const double subtraction=-std::expm1(0.5*std::log(p.effective_gap/tangential_cutoff));
            p.Ct=pi*viscosity*std::sqrt(2*p.effective_radius/p.effective_gap)*subtraction;
        }
    }
    if (!(p.Rn>=0) || !(p.Ct>=0) || !std::isfinite(p.Rn) || !std::isfinite(p.Ct))
        throw std::runtime_error("NearField nonfinite or negative resistance coefficient");
    return p;
}

void NearField::apply(std::vector<Body>& bodies,double dt) {
    if (!(dt>=0) || !std::isfinite(dt))
        throw std::invalid_argument("NearField timestep must be finite and nonnegative");
    validateSettings();
    std::unordered_set<int> ids;
    for (const Body& b:bodies) {
        validateBody(b);
        if (!ids.insert(b.id).second) throw std::invalid_argument("NearField needs unique body IDs");
    }
    stats=Diagnostics{};
    pair_table.clear();
    impulse.assign(bodies.size(),BodyImpulse{});
    stats.kinetic_before=kinetic(bodies);
    stats.kinetic_after=stats.kinetic_before;

    constexpr std::size_t absent=std::numeric_limits<std::size_t>::max();
    std::vector<std::size_t> base(bodies.size(),absent);
    for (std::size_t i=0;i<bodies.size();++i) if (!bodies[i].fixed) {
        base[i]=3*stats.mobile_bodies++;
    }
    const std::size_t ndof=3*stats.mobile_bodies;
    stats.solve_dofs=ndof;
    if (!enabled) return;

    for (std::size_t i=0;i<bodies.size();++i) for (std::size_t j=i+1;j<bodies.size();++j) {
        if (bodies[i].fixed && bodies[j].fixed) continue;
        const PairResistance p=pair_resistance(bodies[i],bodies[j]);
        if (!(p.Rn>0) && !(p.Ct>0)) continue;
        pair_table.push_back({i,j,p});
        ++stats.active_pairs;
        stats.active_modes+=(p.Rn>0 ? 1 : 0)+(p.Ct>0 ? 2 : 0);
        stats.minimum_gap=stats.active_pairs==1 ? p.gap : std::min(stats.minimum_gap,p.gap);
    }
    if (dt==0 || pair_table.empty() || ndof==0) return;
    if (ndof>std::numeric_limits<std::size_t>::max()/ndof)
        throw std::invalid_argument("NearField dense matrix size overflow");

    std::vector<double> inv_sqrt_mass(ndof),zstar(ndof);
    for (std::size_t i=0;i<bodies.size();++i) if (base[i]!=absent) {
        const std::size_t k=base[i];
        const double root_m=std::sqrt(bodies[i].mass),root_i=std::sqrt(bodies[i].inertia);
        inv_sqrt_mass[k]=inv_sqrt_mass[k+1]=1/root_m;
        inv_sqrt_mass[k+2]=1/root_i;
        zstar[k]=root_m*bodies[i].v.x;
        zstar[k+1]=root_m*bodies[i].v.y;
        zstar[k+2]=root_i*bodies[i].omega;
    }
    std::vector<double> matrix(ndof*ndof,0);
    for (std::size_t i=0;i<ndof;++i) matrix[i*ndof+i]=1;
    for (const PairEntry& entry:pair_table) {
        std::array<std::size_t,6> index{};
        for (int k=0;k<3;++k) {
            index[k]=base[entry.a]==absent ? absent : base[entry.a]+k;
            index[k+3]=base[entry.b]==absent ? absent : base[entry.b]+k;
        }
        const std::array<double,3> coefficients={entry.resistance.Rn,entry.resistance.Ct,entry.resistance.Ct};
        for (int mode=0;mode<3;++mode) {
            if (coefficients[mode]==0) continue;
            for (int i=0;i<6;++i) if (index[i]!=absent) {
                const double ci=entry.resistance.modes[mode][i]*inv_sqrt_mass[index[i]];
                for (int j=0;j<=i;++j) if (index[j]!=absent) {
                    const double cj=entry.resistance.modes[mode][j]*inv_sqrt_mass[index[j]];
                    // Body indices and their DOFs are ordered, so this fills
                    // only the lower triangle needed by Cholesky.
                    matrix[index[i]*ndof+index[j]]+=dt*coefficients[mode]*ci*cj;
                }
            }
        }
    }
    std::vector<double> z=zstar;
    choleskySolve(matrix,z);
    const std::vector<Body> before=bodies;
    for (std::size_t i=0;i<bodies.size();++i) if (base[i]!=absent) {
        const std::size_t k=base[i];
        bodies[i].v={z[k]*inv_sqrt_mass[k],z[k+1]*inv_sqrt_mass[k+1]};
        bodies[i].omega=z[k+2]*inv_sqrt_mass[k+2];
    }

    for (const PairEntry& entry:pair_table) {
        const auto velocity=pairVelocity(bodies[entry.a],bodies[entry.b]);
        const std::array<double,3> coefficients={entry.resistance.Rn,entry.resistance.Ct,entry.resistance.Ct};
        std::array<double,6> pair_impulse{};
        for (int mode=0;mode<3;++mode) {
            const double q=dot6(entry.resistance.modes[mode],velocity);
            const double impulse_scale=-dt*coefficients[mode]*q;
            stats.physical_dissipation+=dt*coefficients[mode]*q*q;
            for (int k=0;k<6;++k) pair_impulse[k]+=impulse_scale*entry.resistance.modes[mode][k];
        }
        impulse[entry.a].linear+=Vec2{pair_impulse[0],pair_impulse[1]};
        impulse[entry.a].angular+=pair_impulse[2];
        impulse[entry.b].linear+=Vec2{pair_impulse[3],pair_impulse[4]};
        impulse[entry.b].angular+=pair_impulse[5];
    }
    Vec2 sum_impulse;
    double sum_angular=0,scale=1;
    for (std::size_t i=0;i<bodies.size();++i) {
        impulse[i].angular_global=cross(bodies[i].x,impulse[i].linear)+impulse[i].angular;
        sum_impulse+=impulse[i].linear;
        sum_angular+=impulse[i].angular_global;
        if (base[i]==absent) continue;
        const std::size_t k=base[i];
        const Vec2 dv=bodies[i].v-before[i].v;
        const double dw=bodies[i].omega-before[i].omega;
        stats.numerical_dissipation+=0.5*bodies[i].mass*dot(dv,dv)+0.5*bodies[i].inertia*dw*dw;
        const std::array<double,3> J={impulse[i].linear.x,impulse[i].linear.y,impulse[i].angular};
        for (int component=0;component<3;++component) {
            const double residual=z[k+component]-zstar[k+component]-inv_sqrt_mass[k+component]*J[component];
            stats.solve_residual=std::max(stats.solve_residual,std::abs(residual));
            scale=std::max(scale,std::abs(zstar[k+component]));
        }
    }
    stats.solve_residual/=scale;
    stats.kinetic_after=kinetic(bodies);
    stats.energy_residual=stats.kinetic_after-stats.kinetic_before+
        stats.physical_dissipation+stats.numerical_dissipation;
    stats.linear_balance=norm(sum_impulse);
    stats.angular_balance=std::abs(sum_angular);
    for (double value : {stats.physical_dissipation,stats.numerical_dissipation,
                         stats.energy_residual,stats.solve_residual,
                         stats.linear_balance,stats.angular_balance})
        if (!std::isfinite(value)) throw std::runtime_error("NearField nonfinite impulse or energy diagnostic");
}

} // namespace ibdem
