#include "lbm.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace ibdem {
namespace {

int checked_size(int nx, int ny) {
    if (nx <= 0 || ny <= 0 || nx > std::numeric_limits<int>::max()/ny) {
        throw std::invalid_argument("LBM dimensions must be positive and their product must fit int");
    }
    const auto count = static_cast<std::size_t>(nx)*static_cast<std::size_t>(ny);
    if (count > std::vector<double>().max_size()/LBM::q_count) {
        throw std::invalid_argument("LBM population array is too large");
    }
    return static_cast<int>(count);
}

double checked_tau(double tau) {
    if (!std::isfinite(tau) || tau <= 0.5) {
        throw std::invalid_argument("LBM tau_plus must be finite and greater than 0.5");
    }
    return tau;
}

double checked_magic(double magic) {
    if (!std::isfinite(magic) || magic <= 0.0) {
        throw std::invalid_argument("LBM TRT magic parameter must be finite and positive");
    }
    return magic;
}

double checked_tau_minus(double tau, double magic) {
    const double value = 0.5 + magic/(tau - 0.5);
    if (!std::isfinite(value) || value <= 0.5) {
        throw std::invalid_argument("LBM parameters produce an invalid odd relaxation time");
    }
    return value;
}

bool finite(Vec2 v) {
    return std::isfinite(v.x) && std::isfinite(v.y);
}

void validate_initial_value(Vec2 velocity, double density) {
    if (!finite(velocity) || !std::isfinite(density) || density <= 0.0) {
        throw std::invalid_argument("LBM initialization requires finite velocity and positive finite density");
    }
}

} // namespace

LBM::LBM(int nx_, int ny_, double tau_plus_, double magic_)
    : nx(nx_), ny(ny_), n(checked_size(nx_, ny_)),
      tau_plus(checked_tau(tau_plus_)), magic(checked_magic(magic_)),
      tau_minus(checked_tau_minus(tau_plus, magic)),
      rho(static_cast<std::size_t>(n)), u(static_cast<std::size_t>(n)),
      f(static_cast<std::size_t>(q_count)*n), next_(f.size()),
      omega_plus_(1.0/tau_plus), omega_minus_(1.0/tau_minus) {
    initialize();
}

std::array<double, LBM::q_count> LBM::equilibrium(double density, Vec2 velocity) {
    std::array<double, q_count> eq{};
    const double base = 1.0 - 1.5*dot(velocity, velocity);
    for (int q = 0; q < q_count; ++q) {
        const double cu = cx[q]*velocity.x + cy[q]*velocity.y;
        eq[q] = weight[q]*density*(base + 3.0*cu + 4.5*cu*cu);
    }
    return eq;
}

void LBM::initialize(Vec2 velocity, double density) {
    validate_initial_value(velocity, density);
    const auto eq = equilibrium(density, velocity);
    #pragma omp parallel for if(n >= 16384) schedule(static)
    for (int i = 0; i < n; ++i) {
        rho[i] = density;
        u[i] = velocity;
        for (int q = 0; q < q_count; ++q) {
            f[static_cast<std::size_t>(q)*n + i] = eq[q];
        }
    }
}

void LBM::initialize(const std::vector<Vec2>& velocities, double density) {
    if (velocities.size() != static_cast<std::size_t>(n)) {
        throw std::invalid_argument("LBM initial velocity field has the wrong size");
    }
    validate_initial_value({}, density);
    for (Vec2 velocity : velocities) {
        validate_initial_value(velocity, density);
    }
    #pragma omp parallel for if(n >= 16384) schedule(static)
    for (int i = 0; i < n; ++i) {
        rho[i] = density;
        u[i] = velocities[i];
        const auto eq = equilibrium(density, velocities[i]);
        for (int q = 0; q < q_count; ++q) {
            f[static_cast<std::size_t>(q)*n + i] = eq[q];
        }
    }
}

void LBM::macros() {
    int invalid = 0;
    #pragma omp parallel for if(n >= 16384) schedule(static) reduction(|:invalid)
    for (int i = 0; i < n; ++i) {
        double r = 0.0;
        for (int q = 0; q < q_count; ++q) {
            r += f[static_cast<std::size_t>(q)*n + i];
        }
        const double px = (f[static_cast<std::size_t>(1)*n+i] - f[static_cast<std::size_t>(3)*n+i])
                        + (f[static_cast<std::size_t>(5)*n+i] - f[static_cast<std::size_t>(7)*n+i])
                        + (f[static_cast<std::size_t>(8)*n+i] - f[static_cast<std::size_t>(6)*n+i]);
        const double py = (f[static_cast<std::size_t>(2)*n+i] - f[static_cast<std::size_t>(4)*n+i])
                        + (f[static_cast<std::size_t>(5)*n+i] - f[static_cast<std::size_t>(7)*n+i])
                        + (f[static_cast<std::size_t>(6)*n+i] - f[static_cast<std::size_t>(8)*n+i]);
        rho[i] = r;
        if (!(r > 0.0) || !std::isfinite(r) || !std::isfinite(px) || !std::isfinite(py)) {
            invalid = 1;
            u[i] = {};
        } else {
            u[i] = {px/r, py/r};
            if (!finite(u[i])) invalid = 1;
        }
    }
    if (invalid) {
        throw std::runtime_error("LBM encountered a nonpositive density or nonfinite macroscopic state");
    }
}

void LBM::collide_stream() {
    // Each (q, source cell) maps to one unique (q, destination cell), so the
    // push scheme has no cross-thread writes to the same population.
    #pragma omp parallel for if(n >= 16384) schedule(static)
    for (int i = 0; i < n; ++i) {
        const auto eq = equilibrium(rho[i], u[i]);
        std::array<double, q_count> post{};
        post[0] = f[i] - omega_plus_*(f[i] - eq[0]);
        constexpr std::array<int, 4> pairs{{1, 2, 5, 6}};
        for (int q : pairs) {
            const int p = opposite[q];
            const double fq = f[static_cast<std::size_t>(q)*n+i];
            const double fp = f[static_cast<std::size_t>(p)*n+i];
            const double even = 0.5*omega_plus_*((fq+fp) - (eq[q]+eq[p]));
            const double odd = 0.5*omega_minus_*((fq-fp) - (eq[q]-eq[p]));
            post[q] = fq - even - odd;
            post[p] = fp - even + odd;
        }

        const int y = i/nx;
        const int x = i-y*nx;
        const int xp = x+1 == nx ? 0 : x+1;
        const int xm = x == 0 ? nx-1 : x-1;
        const int yp = (y+1 == ny ? 0 : y+1)*nx;
        const int ym = (y == 0 ? ny-1 : y-1)*nx;
        const int row = y*nx;
        const std::array<int, q_count> destination{{
            i, row+xp, yp+x, row+xm, ym+x, yp+xp, yp+xm, ym+xm, ym+xp
        }};
        for (int q = 0; q < q_count; ++q) {
            next_[static_cast<std::size_t>(q)*n + destination[q]] = post[q];
        }
    }
    f.swap(next_);
    macros();
}

double LBM::periodic_angular_flux() const {
    long double change=0.0L;
    for (int q=0; q<q_count; ++q) {
        // Axial populations cannot change angular momentum through a wrap:
        // their coordinate jump is parallel to the carried momentum.
        if (cx[q]==0 || cy[q]==0) continue;
        const std::size_t offset=static_cast<std::size_t>(q)*n;
        const int x_destination=cx[q]>0 ? 0 : nx-1;
        const long double x_coefficient=-static_cast<long double>(nx)*cx[q]*cy[q];
        for (int y=0; y<ny; ++y)
            change+=x_coefficient*f[offset+static_cast<std::size_t>(y)*nx+x_destination];
        const int y_destination=cy[q]>0 ? 0 : ny-1;
        const long double y_coefficient=static_cast<long double>(ny)*cy[q]*cx[q];
        for (int x=0; x<nx; ++x)
            change+=y_coefficient*f[offset+static_cast<std::size_t>(y_destination)*nx+x];
        // A corner population appears in both sums because both periodic
        // coordinate shifts change its angular momentum about this origin.
    }
    return static_cast<double>(change);
}

void LBM::apply_impulse(const std::vector<Vec2>& impulse) {
    if (impulse.size() != static_cast<std::size_t>(n)) {
        throw std::invalid_argument("LBM impulse field has the wrong size");
    }
    // Validate before modifying any population. Cached rho/u are maintained by
    // all public evolution methods; external population edits require macros().
    for (int i = 0; i < n; ++i) {
        if (!finite(impulse[i]) || !finite(u[i]) || !std::isfinite(rho[i]) || rho[i] <= 0.0) {
            throw std::invalid_argument("LBM impulse requires finite fields and positive density");
        }
        if (!finite(u[i] + impulse[i]/rho[i])) {
            throw std::invalid_argument("LBM impulse would produce nonfinite velocity");
        }
    }
    #pragma omp parallel for if(n >= 16384) schedule(static)
    for (int i = 0; i < n; ++i) {
        if (impulse[i].x == 0.0 && impulse[i].y == 0.0) continue;
        const Vec2 updated = u[i] + impulse[i]/rho[i];
        const auto old_eq = equilibrium(rho[i], u[i]);
        const auto new_eq = equilibrium(rho[i], updated);
        for (int q = 0; q < q_count; ++q) {
            f[static_cast<std::size_t>(q)*n+i] += new_eq[q] - old_eq[q];
        }
        u[i] = updated;
    }
}

void LBM::apply_indexed_impulse(const std::vector<int>& nodes, const std::vector<Vec2>& impulses) {
    if (nodes.size()!=impulses.size()) throw std::invalid_argument("Indexed impulse shape mismatch");
    int last=-1;
    for (std::size_t k=0;k<nodes.size();++k) {
        const int i=nodes[k];
        if (i<=last || i>=n) throw std::invalid_argument("Impulse indices must be in range, sorted and unique");
        last=i;
        if (!finite(impulses[k]) || !finite(u[i]) || !(rho[i]>0) || !std::isfinite(rho[i]) ||
            !finite(u[i]+impulses[k]/rho[i])) throw std::invalid_argument("Nonfinite touched cell in indexed impulse");
    }
    // Same full equilibrium difference as the dense version. Streaming already
    // validates macros across the entire grid; here only touched cells can change.
    for (std::size_t k=0;k<nodes.size();++k) {
        Vec2 impulse=impulses[k]; if(impulse.x==0.0 && impulse.y==0.0) continue;
        const int i=nodes[k];
        const Vec2 updated=u[i]+impulse/rho[i];
        const auto old_eq=equilibrium(rho[i],u[i]);
        const auto new_eq=equilibrium(rho[i],updated);
        for(int q=0;q<q_count;++q) f[static_cast<std::size_t>(q)*n+i]+=new_eq[q]-old_eq[q];
        u[i]=updated;
    }
}

} // namespace ibdem
