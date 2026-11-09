#pragma once
#include <cmath>
#include <vector>
#include <stdexcept>

namespace ibdem {
constexpr double pi = 3.1415926535897932384626433832795;
struct Vec2 {
    double x=0.0, y=0.0;
    Vec2()=default; Vec2(double a,double b):x(a),y(b){}
    Vec2 operator+(Vec2 b) const {return {x+b.x,y+b.y};}
    Vec2 operator-(Vec2 b) const {return {x-b.x,y-b.y};}
    Vec2 operator-() const {return {-x,-y};}
    Vec2 operator*(double a) const {return {a*x,a*y};}
    Vec2 operator/(double a) const {return {x/a,y/a};}
    Vec2& operator+=(Vec2 b){x+=b.x;y+=b.y;return *this;}
    Vec2& operator-=(Vec2 b){x-=b.x;y-=b.y;return *this;}
    Vec2& operator*=(double a){x*=a;y*=a;return *this;}
};
inline Vec2 operator*(double a,Vec2 v){return v*a;}
inline double dot(Vec2 a,Vec2 b){return a.x*b.x+a.y*b.y;}
inline double cross(Vec2 a,Vec2 b){return a.x*b.y-a.y*b.x;}
inline double norm(Vec2 a){return std::sqrt(dot(a,a));}
inline Vec2 perp(Vec2 a){return {-a.y,a.x};}
struct Body {
    int id=0;
    Vec2 x, v;
    double angle=0.0, omega=0.0;
    // radius is the smooth hydrodynamic/core radius. contact_offset is an
    // explicitly declared radial asperity reach, not a numerical stiffness or
    // mass correction. Its contact envelope does not change mass or inertia.
    double radius=1.0, contact_offset=0.0, mass=1.0, inertia=0.5;
    bool fixed=false;
    Vec2 force;
    double torque=0.0;
    double contactRadius() const { return radius+contact_offset; }
};
inline Body disk(int id,Vec2 x,double r,double density,bool fixed=false,
                 double contact_offset=0.0){
    if(!(r>0.0 && density>0.0)) throw std::invalid_argument("Positive radius and density required");
    if(!(contact_offset>=0.0) || !std::isfinite(contact_offset) ||
       !std::isfinite(r+contact_offset))
        throw std::invalid_argument("Finite nonnegative contact offset required");
    Body b; b.id=id;b.x=x;b.radius=r;b.contact_offset=contact_offset;b.mass=density*pi*r*r;
    b.inertia=0.5*b.mass*r*r;b.fixed=fixed;return b;
}
}
