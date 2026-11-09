#include "dem.hpp"
#include <algorithm>
#include <limits>
#include <unordered_set>

namespace ibdem {
namespace {

struct Contact {
    Vec2 n, t;
    double overlap=0.0, la=0.0, lb=0.0, vn=0.0, vt=0.0;
    bool touching=false;
};

bool finite(Vec2 v) { return std::isfinite(v.x) && std::isfinite(v.y); }
Vec2 velocity(const Body& b) { return b.fixed ? Vec2{} : b.v; }
double spin(const Body& b) { return b.fixed ? 0.0 : b.omega; }

Contact geometry(const Body& a, const Body& b) {
    Contact c;
    const Vec2 dx=b.x-a.x;
    const double r=norm(dx);
    const double ra=a.contactRadius(), rb=b.contactRadius();
    c.overlap=ra+rb-r;
    if (c.overlap<0.0) return c;
    if (!(r>std::abs(ra-rb)))
        throw std::runtime_error("DEM: coincident/contained disks; reduce the timestep or repair the initial geometry");
    c.n=dx/r;
    c.t=perp(c.n);
    c.la=0.5*(r+ra-rb);
    c.lb=r-c.la;
    const Vec2 dv=velocity(a)-velocity(b);
    c.vn=dot(dv,c.n);
    c.vt=dot(dv,c.t)+c.la*spin(a)+c.lb*spin(b);
    c.touching=c.overlap>0.0 || c.vn>0.0;
    return c;
}

// Used for slip quadrature, including a newly forming contact's event interval.
double slipAt(const Body& a0, const Body& b0,
              const Body& a1, const Body& b1, double s) {
    const Vec2 xa=a0.x+(a1.x-a0.x)*s;
    const Vec2 xb=b0.x+(b1.x-b0.x)*s;
    const Vec2 dx=xb-xa;
    const double r=norm(dx);
    const double ra=a0.contactRadius(), rb=b0.contactRadius();
    if (!(r>std::abs(ra-rb)))
        throw std::runtime_error("DEM: invalid geometry during contact-history quadrature");
    const Vec2 n=dx/r, t=perp(n);
    const double la=0.5*(r+ra-rb), lb=r-la;
    const Vec2 va=velocity(a0)+(velocity(a1)-velocity(a0))*s;
    const Vec2 vb=velocity(b0)+(velocity(b1)-velocity(b0))*s;
    const double wa=spin(a0)+(spin(a1)-spin(a0))*s;
    const double wb=spin(b0)+(spin(b1)-spin(b0))*s;
    return dot(va-vb,t)+la*wa+lb*wb;
}

double normalForce(const Contact& c, double kn, double cn) {
    return c.touching ? std::max(0.0,kn*c.overlap+cn*c.vn) : 0.0;
}

double tangentialForce(double xi, double vt, double fn,
                       double kt, double ct, double mu) {
    if (!(fn>0.0) || mu==0.0) return 0.0;
    return std::clamp(-kt*xi-ct*vt,-mu*fn,mu*fn);
}

double returnMappedHistory(double old_xi, double xi, double vt, double fn,
                           double kt, double ct, double mu, double dt) {
    if (!(fn>0.0) || !(kt>0.0) || !(mu>0.0)) return 0.0;
    const double trial=-kt*xi-ct*vt;
    const double cap=mu*fn;
    if (std::abs(trial)>cap) {
        const double direction=trial<0.0 ? 1.0 : -1.0;
        // Backward-Euler return map of a Kelvin-Voigt element in series
        // with the Coulomb slider. For ct=0 it returns xi=+/-cap/kt.
        // Setting xi=-(Ft+ct*vt)/kt instead would use total slip rather
        // than elastic slip in the dashpot and can inject spring energy.
        return (ct*old_xi+dt*cap*direction)/(ct+dt*kt);
    }
    return xi;
}

} // namespace

DEM::Pair DEM::key(int a, int b) { return a<b ? Pair{a,b} : Pair{b,a}; }

void DEM::validate(const std::vector<Body>& bodies) const {
    for (double p : {kn,kt,cn,ct,mu})
        if (!(p>=0.0) || !std::isfinite(p))
            throw std::invalid_argument("DEM parameters must be finite and nonnegative");
    std::unordered_set<int> ids;
    for (const Body& b : bodies) {
        if (!ids.insert(b.id).second)
            throw std::invalid_argument("DEM requires unique, stable Body IDs");
        if (!(b.radius>0.0) || !std::isfinite(b.radius) || !finite(b.x) ||
            !finite(b.v) || !std::isfinite(b.angle) || !std::isfinite(b.omega))
            throw std::invalid_argument("DEM body geometry and velocity must be finite");
        if (!(b.contact_offset>=0.0) || !std::isfinite(b.contact_offset) ||
            !std::isfinite(b.contactRadius()))
            throw std::invalid_argument("DEM contact offsets must be finite and nonnegative");
        if (!b.fixed && (!(b.mass>0.0) || !(b.inertia>0.0) ||
                         !std::isfinite(b.mass) || !std::isfinite(b.inertia)))
            throw std::invalid_argument("DEM moving bodies require positive finite mass and inertia");
    }
}

double DEM::tangentialHistory(int id_a, int id_b) const {
    const auto it=history_.find(key(id_a,id_b));
    return it==history_.end() ? 0.0 : it->second;
}

void DEM::evaluate(std::vector<Body>& bodies, double dt) {
    if (!(dt>=0.0) || !std::isfinite(dt))
        throw std::invalid_argument("DEM history timestep must be finite and nonnegative");
    validate(bodies);
    ++force_evaluations;
    stats=Diagnostics{};
    for (Body& b : bodies) { b.force={}; b.torque=0.0; }
    std::unordered_set<Pair,PairHash> live;
    for (std::size_t i=0;i<bodies.size();++i) {
        for (std::size_t j=i+1;j<bodies.size();++j) {
            if (bodies[i].fixed && bodies[j].fixed) continue;
            Body& a=bodies[bodies[i].id<bodies[j].id ? i : j];
            Body& b=bodies[bodies[i].id<bodies[j].id ? j : i];
            const Contact c=geometry(a,b);
            if (!c.touching) continue;
            ++stats.contact_count;
            stats.max_overlap=std::max(stats.max_overlap,c.overlap);
            stats.elastic_energy+=0.5*kn*c.overlap*c.overlap;
            const Pair pair=key(a.id,b.id);
            const double fn=normalForce(c,kn,cn);
            double xi=tangentialHistory(a.id,b.id);
            if (fn>0.0 && kt>0.0 && mu>0.0) {
                live.insert(pair);
                if (dt>0.0) {
                    xi=returnMappedHistory(xi,xi+dt*c.vt,c.vt,fn,kt,ct,mu,dt);
                    history_[pair]=xi;
                }
                stats.elastic_energy+=0.5*kt*xi*xi;
            } else {
                xi=0.0;
            }
            const double ft=tangentialForce(xi,c.vt,fn,kt,ct,mu);
            const Vec2 f=-fn*c.n+ft*c.t;
            a.force+=f;
            b.force-=f;
            a.torque+=c.la*ft;
            b.torque+=c.lb*ft;
            if (fn>0.0) {
                ++stats.force_count;
                stats.max_friction_ratio=std::max(stats.max_friction_ratio,std::abs(ft)/fn);
            }
        }
    }
    for (auto it=history_.begin();it!=history_.end();) {
        if (live.find(it->first)==live.end()) it=history_.erase(it);
        else ++it;
    }
}

void DEM::advanceHistory(const std::vector<Body>& old_bodies,
                         const std::vector<Body>& predicted_bodies, double dt) {
    std::unordered_map<Pair,double,PairHash> next;
    if (kt==0.0 || mu==0.0) { history_.clear(); return; }
    for (std::size_t i=0;i<predicted_bodies.size();++i) {
        for (std::size_t j=i+1;j<predicted_bodies.size();++j) {
            if (predicted_bodies[i].fixed && predicted_bodies[j].fixed) continue;
            const std::size_t ia=predicted_bodies[i].id<predicted_bodies[j].id ? i : j;
            const std::size_t ib=ia==i ? j : i;
            const Body& a=predicted_bodies[ia];
            const Body& b=predicted_bodies[ib];
            const Contact c=geometry(a,b);
            const double fn=normalForce(c,kn,cn);
            if (!(fn>0.0)) continue;
            const Body& a0=old_bodies[ia];
            const Body& b0=old_bodies[ib];
            const double old_overlap=a0.contactRadius()+b0.contactRadius()-norm(b0.x-a0.x);
            double fraction=1.0;
            if (old_overlap<0.0)
                fraction=std::clamp(c.overlap/(c.overlap-old_overlap),0.0,1.0);
            // Midpoint of the active portion of the step. This prevents adding
            // an entire timestep of slip before two previously separated disks
            // first touch. It is an event approximation, not an exact locator.
            const double s=1.0-0.5*fraction;
            const double vt=slipAt(a0,b0,a,b,s);
            const double old_xi=old_overlap>=0.0 ? tangentialHistory(a.id,b.id) : 0.0;
            const double active_dt=dt*fraction;
            const double xi=active_dt>0.0
                ? returnMappedHistory(old_xi,old_xi+active_dt*vt,vt,fn,kt,ct,mu,active_dt)
                : old_xi;
            next[key(a.id,b.id)]=xi;
        }
    }
    history_.swap(next);
}

void DEM::advance(std::vector<Body>& bodies, double dt, int substeps,
                  const std::vector<Vec2>& external,
                  const std::vector<double>& externalTorque) {
    if (!(dt>=0.0) || !std::isfinite(dt) || substeps<1)
        throw std::invalid_argument("DEM advance needs finite dt>=0 and substeps>=1");
    if ((!external.empty() && external.size()!=bodies.size()) ||
        (!externalTorque.empty() && externalTorque.size()!=bodies.size()))
        throw std::invalid_argument("DEM external force/torque size must match bodies");
    for (Vec2 f : external)
        if (!finite(f)) throw std::invalid_argument("DEM external forces must be finite");
    for (double t : externalTorque)
        if (!std::isfinite(t)) throw std::invalid_argument("DEM external torques must be finite");
    validate(bodies);
    if (dt==0.0) { evaluate(bodies,0.0); return; }
    const double h=dt/substeps;
    const auto ef=[&](std::size_t i) { return external.empty() ? Vec2{} : external[i]; };
    const auto et=[&](std::size_t i) { return externalTorque.empty() ? 0.0 : externalTorque[i]; };
    for (int step=0;step<substeps;++step) {
        evaluate(bodies,0.0);
        const std::vector<Body> old=bodies;
        for (std::size_t i=0;i<bodies.size();++i) {
            Body& b=bodies[i];
            if (b.fixed) continue;
            b.v+=(b.force+ef(i))*(0.5*h/b.mass);
            b.omega+=(b.torque+et(i))*(0.5*h/b.inertia);
            b.x+=b.v*h;
            b.angle+=b.omega*h;
        }
        std::vector<Body> predicted=bodies;
        for (std::size_t i=0;i<bodies.size();++i) {
            if (bodies[i].fixed) continue;
            predicted[i].v+=(old[i].force+ef(i))*(0.5*h/old[i].mass);
            predicted[i].omega+=(old[i].torque+et(i))*(0.5*h/old[i].inertia);
        }
        advanceHistory(old,predicted,h);
        evaluate(predicted,0.0);
        for (std::size_t i=0;i<bodies.size();++i) {
            Body& b=bodies[i];
            b.force=predicted[i].force;
            b.torque=predicted[i].torque;
            if (b.fixed) continue;
            b.v+=(b.force+ef(i))*(0.5*h/b.mass);
            b.omega+=(b.torque+et(i))*(0.5*h/b.inertia);
        }
        // Report forces at the accepted velocity, not at the predictor. The
        // contact history is not integrated a second time by this query.
        evaluate(bodies,0.0);
    }
}

} // namespace ibdem
