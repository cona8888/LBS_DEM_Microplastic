#pragma once

#include <cmath>
#include <initializer_list>
#include <stdexcept>

namespace ibdem {

// A standalone finite two-port Reynolds element. Units may be SI or another
// consistent system. Forces, fluxes and powers are per unit axial length.
// Full gap h>0, -half_length <= x <= +half_length; t=e_z x n, n from a to b.
// No IBM, particle advancement, cavitation treatment or outer pressure solve.
struct FilmPortInput {
    double radius_a=0, radius_b=0, h=0, half_length=0, viscosity=0;
    double va_t=0, vb_t=0, omega_a=0, omega_b=0;
    double closing_speed=0; // -dh/dt; positive on approach
    double pressure_left=0, pressure_right=0;
};

struct FilmPortResult {
    double effective_radius=0, gap_frame_velocity=0;
    double wall_speed_a=0, wall_speed_b=0; // in the translating gap frame
    double conductance=0, center_flux=0;   // conductance = dQ/d(Pleft-Pright)
    double outward_left=0, outward_right=0, area=0, area_rate=0, volume_residual=0;
    double shear_on_fluid_a=0, shear_on_fluid_b=0; // NOT total rigid-body loads
    double pressure_integral=0;                    // integral P dx
    double port_power=0, shear_power=0, squeeze_power=0, total_power_in=0;
    double dissipation_shear=0, dissipation_pressure=0, dissipation=0, power_residual=0;
};

class ReynoldsFilmPort {
    using W=long double;
    FilmPortInput in_;
    W a_, b_, h_, L_, mu_, vn_, pl_, pr_, r_, ell_, limit_, c_, ua_, ub_, m_, s_;
    W j0_, ratio_, i1_, ix2_, variance_, g_, qp_, q0_;

    struct Moments { W j0,j2,j4; };
    static Moments moments(W t) {
        // Integral of z^n/(1+z^2)^3, 0..t, n=0,2,4. The short-interval
        // series avoids cancellation in the trigonometric differences.
        if (std::abs(t)<0.25L) {
            W sum[3]={}, power=1;
            for (int k=0;k<32;++k) {
                const W coeff=static_cast<W>((k+1)*(k+2))*0.5L*power;
                for(int j=0;j<3;++j) sum[j]+=coeff/(2*k+2*j+1);
                power*=-t*t;
            }
            const W t2=t*t;
            return {t*sum[0],t*t2*sum[1],t*t2*t2*sum[2]};
        }
        const W theta=std::atan(t), s2=std::sin(2*theta), s4=std::sin(4*theta);
        return {3*theta/8+s2/4+s4/32, theta/8-s4/32,
                3*theta/8-s2/4+s4/32};
    }
    static double out(W v) {
        const double d=static_cast<double>(v);
        if (!std::isfinite(d) || (v!=0 && d==0))
            throw std::range_error("FilmPort result outside representable double range");
        return d;
    }
    W coord(double x) const {
        if (!std::isfinite(x) || std::abs(static_cast<W>(x))>L_)
            throw std::out_of_range("FilmPort sample outside its finite interval");
        return x;
    }

public:
    explicit ReynoldsFilmPort(const FilmPortInput& v): in_(v),
            a_(v.radius_a),b_(v.radius_b),h_(v.h),L_(v.half_length),
            mu_(v.viscosity),vn_(v.closing_speed),pl_(v.pressure_left),pr_(v.pressure_right) {
        for (double z:{v.radius_a,v.radius_b,v.h,v.half_length,v.viscosity})
            if (!(z>0) || !std::isfinite(z))
                throw std::invalid_argument("FilmPort requires positive finite radii, gap, half-length and viscosity");
        for (double z:{v.va_t,v.vb_t,v.omega_a,v.omega_b,v.closing_speed,v.pressure_left,v.pressure_right})
            if (!std::isfinite(z)) throw std::invalid_argument("FilmPort state must be finite");
        r_=(a_<=b_ ? a_/(1+a_/b_) : b_/(1+b_/a_));
        ell_=std::sqrt(2*r_*h_); limit_=L_/ell_;
        const W wa=a_/(a_+b_), wb=b_/(a_+b_);
        const W dv=static_cast<W>(v.va_t)-v.vb_t;
        c_=wb*v.va_t+wa*v.vb_t;
        ua_=wa*dv+a_*v.omega_a; ub_=-wb*dv-b_*v.omega_b;
        m_=(ua_+ub_)/2; s_=ua_-ub_;
        const Moments j=moments(limit_);
        j0_=j.j0; ratio_=j.j2/j0_;
        const W i3=2*ell_*j0_/(h_*h_*h_);
        g_=1/(12*mu_*i3);
        i1_=2*ell_*(j0_+2*j.j2+j.j4)/h_;
        ix2_=2*(ell_/h_)*(ell_/h_)*(ell_/h_)*j.j2;
        variance_=2*ell_*(j.j4-j.j2*ratio_)/h_; // I1-I2^2/I3
        if (!(g_>0 && i1_>0 && ix2_>0 && variance_>=0) ||
            !std::isfinite(g_) || !std::isfinite(i1_) ||
            !std::isfinite(ix2_) || !std::isfinite(variance_))
            throw std::range_error("FilmPort integral scaling outside representable range");
        qp_=g_*(pl_-pr_); q0_=m_*h_*(1+ratio_)+qp_;
    }
    const FilmPortInput& input() const { return in_; }
    double gap(double x) const {
        const W z=coord(x)/ell_; return out(h_*(1+z*z));
    }
    double flux(double x) const {
        return out(q0_+vn_*coord(x)); // positive along +x, relative to the port frame
    }
    double pressure_gradient(double x) const {
        const W X=coord(x), z=X/ell_, H=h_*(1+z*z);
        return out(-12*mu_*(qp_+m_*h_*(ratio_-z*z)+vn_*X)/(H*H*H));
    }
    double pressure(double x) const {
        const W X=coord(x), z=X/ell_, B=limit_*limit_, Z=z*z;
        const Moments j=moments(z);
        const W odd=12*mu_*ell_/(h_*h_*h_)*
            (m_*h_*(j.j2-ratio_*j.j0)-qp_*j.j0);
        const W squeeze=6*mu_*r_*vn_/(h_*h_)*
            ((B-Z)/(1+B))*((2+B+Z)/(1+B))/((1+Z)*(1+Z));
        return out((pl_+pr_)/2+odd+squeeze);
    }
    FilmPortResult evaluate() const {
        FilmPortResult f;
        f.effective_radius=out(r_); f.gap_frame_velocity=out(c_);
        f.wall_speed_a=out(ua_); f.wall_speed_b=out(ub_); f.conductance=out(g_);
        f.center_flux=out(q0_);
        const W left=-(q0_-vn_*L_), right=q0_+vn_*L_, dA=-2*L_*vn_;
        f.outward_left=out(left); f.outward_right=out(right);
        f.area=out(2*L_*h_+L_*L_*L_/(3*r_)); f.area_rate=out(dA);
        f.volume_residual=out(left+right+dA);
        const W dp=pl_-pr_, hbar=h_*(1+ratio_);
        const W hpgrad=12*mu_*m_*variance_-dp*hbar; // integral H dP/dx dx
        const W fa=mu_*s_*i1_+hpgrad/2, fb=-mu_*s_*i1_+hpgrad/2;
        const W pint=L_*(pl_+pr_)+12*mu_*vn_*ix2_;
        const W port=-pl_*left-pr_*right, shear=ua_*fa+ub_*fb, squeeze=vn_*pint;
        const W ds=mu_*s_*s_*i1_;
        const W dpvis=g_*dp*dp+12*mu_*(m_*m_*variance_+vn_*vn_*ix2_);
        const W input=port+shear+squeeze, diss=ds+dpvis;
        f.shear_on_fluid_a=out(fa); f.shear_on_fluid_b=out(fb);
        f.pressure_integral=out(pint);
        f.port_power=out(port); f.shear_power=out(shear); f.squeeze_power=out(squeeze);
        f.total_power_in=out(input); f.dissipation_shear=out(ds);
        f.dissipation_pressure=out(dpvis); f.dissipation=out(diss);
        f.power_residual=out(input-diss); return f;
    }
};

} // namespace ibdem
