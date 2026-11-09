#pragma once

#include "common.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

namespace ibdem {

struct DiskCellMoments {
    double area = 0.0;
    // GLOBAL first area moment: integral_{disk intersect cell} (x,y) dA.
    // This is not the centroid; divide by area only when area is positive.
    Vec2 first{};
};

namespace disk_quadrature_detail {
struct Point {
    long double x = 0.0L, y = 0.0L;
};
struct Integral {
    long double area = 0.0L, mx = 0.0L, my = 0.0L;
};
inline Point add(Point a, Point b) { return {a.x+b.x,a.y+b.y}; }
inline Point scale(Point a, long double s) { return {a.x*s,a.y*s}; }
inline long double dot(Point a, Point b) { return a.x*b.x+a.y*b.y; }
inline long double cross(Point a, Point b) { return a.x*b.y-a.y*b.x; }

// Oriented edge contribution to the intersection of a circle centered at the
// origin and a polygon. Splitting at circle intersections makes each interval
// either a triangle inside the disk or an oriented circular sector outside it.
inline Integral edge_integral(Point a, Point b, long double radius) {
    const Point d{b.x-a.x,b.y-a.y};
    const long double aa=dot(d,d), rr=radius*radius;
    std::array<long double,4> cuts{{0.0L,1.0L,0.0L,0.0L}};
    int count=2;
    if (aa>0.0L) {
        const long double projection=-dot(a,d)/aa;
        const long double cr=cross(a,d);
        const long double gap=rr-cr*cr/aa;
        if (gap>0.0L) {
            const long double offset=std::sqrt(gap/aa);
            for (long double t : {projection-offset,projection+offset}) {
                if (t>0.0L && t<1.0L) cuts[count++]=t;
            }
        }
    }
    std::sort(cuts.begin(),cuts.begin()+count);
    Integral result;
    for (int k=1;k<count;++k) {
        if (cuts[k]<=cuts[k-1]) continue;
        const Point p=add(a,scale(d,cuts[k-1]));
        const Point q=add(a,scale(d,cuts[k]));
        const Point mid=scale(add(p,q),0.5L);
        // Strict inequality matters: an unsplit tangent edge has its midpoint
        // exactly on the circle but contributes a sector, not the full triangle.
        if (dot(mid,mid)<rr) {
            const long double area=0.5L*cross(p,q);
            result.area+=area;
            result.mx+=area*(p.x+q.x)/3.0L;
            result.my+=area*(p.y+q.y)/3.0L;
        } else {
            const long double np=std::hypot(p.x,p.y);
            const long double nq=std::hypot(q.x,q.y);
            // An outside interval cannot contain the origin for radius>0.
            // Its signed polar-angle change has magnitude at most pi.
            const long double angle=std::atan2(cross(p,q),dot(p,q));
            result.area+=0.5L*rr*angle;
            const long double factor=rr*radius/3.0L;
            result.mx+=factor*(q.y/nq-p.y/np);
            result.my+=factor*(p.x/np-q.x/nq);
        }
    }
    return result;
}
} // namespace disk_quadrature_detail

// The unit square cell is [x-1/2,x+1/2] x [y-1/2,y+1/2].
// Analytic geometry is accumulated in long double; the returned values have
// ordinary floating-point roundoff and are not interval-arithmetic bounds.
inline DiskCellMoments disk_cell_moments(Vec2 centre,double radius,int x,int y) {
    if (!std::isfinite(centre.x) || !std::isfinite(centre.y) ||
        !std::isfinite(radius) || radius<=0.0) {
        throw std::invalid_argument("Disk quadrature requires finite center and positive finite radius");
    }
    using namespace disk_quadrature_detail;
    const long double cx=centre.x, cy=centre.y, r=radius;
    const long double dx=std::abs(static_cast<long double>(x)-cx);
    const long double dy=std::abs(static_cast<long double>(y)-cy);
    const long double near_x=std::max(0.0L,dx-0.5L);
    const long double near_y=std::max(0.0L,dy-0.5L);
    if (std::hypot(near_x,near_y)>=r) return {};
    if (std::hypot(dx+0.5L,dy+0.5L)<=r) {
        return {1.0,{static_cast<double>(x),static_cast<double>(y)}};
    }
    const long double left=static_cast<long double>(x)-0.5L-cx;
    const long double right=static_cast<long double>(x)+0.5L-cx;
    const long double bottom=static_cast<long double>(y)-0.5L-cy;
    const long double top=static_cast<long double>(y)+0.5L-cy;
    const std::array<Point,4> vertices{{{left,bottom},{right,bottom},
                                       {right,top},{left,top}}};
    Integral total;
    for (int k=0;k<4;++k) {
        const auto part=edge_integral(vertices[k],vertices[(k+1)%4],r);
        total.area+=part.area;
        total.mx+=part.mx;
        total.my+=part.my;
    }
    // The exact area lies in [0,1]; clipping removes only possible cancellation
    // roundoff. Scale the first moment consistently if the upper bound clips.
    if (total.area<=0.0L) return {};
    const long double area=std::min(1.0L,total.area);
    const long double correction=area/total.area;
    return {static_cast<double>(area),
            {static_cast<double>(cx*area+correction*total.mx),
             static_cast<double>(cy*area+correction*total.my)}};
}

} // namespace ibdem
