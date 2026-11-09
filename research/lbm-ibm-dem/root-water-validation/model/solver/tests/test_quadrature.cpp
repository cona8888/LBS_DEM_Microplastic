#include "disk_quadrature.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {
using ibdem::DiskCellMoments;
using ibdem::Vec2;
using ibdem::disk_cell_moments;

void require(bool condition,const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

void close(double actual,double expected,double tolerance,const std::string& label) {
    if (!std::isfinite(actual) || std::abs(actual-expected)>tolerance) {
        std::ostringstream message;
        message<<std::setprecision(17)<<label<<": actual="<<actual
               <<", expected="<<expected<<", tolerance="<<tolerance;
        throw std::runtime_error(message.str());
    }
}

struct Totals { long double area=0.0L,mx=0.0L,my=0.0L; };

Totals tile(Vec2 centre,double radius) {
    Totals sum;
    const int x0=static_cast<int>(std::floor(centre.x-radius-0.5));
    const int x1=static_cast<int>(std::ceil(centre.x+radius+0.5));
    const int y0=static_cast<int>(std::floor(centre.y-radius-0.5));
    const int y1=static_cast<int>(std::ceil(centre.y+radius+0.5));
    for (int y=y0;y<=y1;++y) for (int x=x0;x<=x1;++x) {
        const auto cell=disk_cell_moments(centre,radius,x,y);
        require(cell.area>=0.0 && cell.area<=1.0,"Disk cell area outside [0,1]");
        if (cell.area>1e-13) {
            const Vec2 centroid=cell.first/cell.area;
            require(centroid.x>=x-0.5-1e-9 && centroid.x<=x+0.5+1e-9 &&
                    centroid.y>=y-0.5-1e-9 && centroid.y<=y+0.5+1e-9,
                    "Intersection centroid outside its cell");
        }
        sum.area+=cell.area;sum.mx+=cell.first.x;sum.my+=cell.first.y;
    }
    return sum;
}

// Independent numerical oracle: vertical slices of the disk clipped to the
// square, integrated by 2^20 midpoint strips. It uses no polygon, triangles,
// sectors, signed-angle sums, or analytic moment routine from the header.
DiskCellMoments numerical_strips(Vec2 centre,double radius,int x,int y) {
    constexpr int strips=1<<20;
    const long double cx=centre.x,cy=centre.y,r=radius;
    const long double lo=std::max(static_cast<long double>(x)-0.5L,cx-r);
    const long double hi=std::min(static_cast<long double>(x)+0.5L,cx+r);
    if (hi<=lo) return {};
    const long double h=(hi-lo)/strips;
    Totals sum;
    for (int k=0;k<strips;++k) {
        const long double xx=lo+(static_cast<long double>(k)+0.5L)*h;
        const long double half=std::sqrt(std::max(0.0L,r*r-(xx-cx)*(xx-cx)));
        const long double yl=std::max(static_cast<long double>(y)-0.5L,cy-half);
        const long double yu=std::min(static_cast<long double>(y)+0.5L,cy+half);
        if (yu<=yl) continue;
        const long double width=yu-yl;
        sum.area+=width;
        sum.mx+=xx*width;
        sum.my+=0.5L*(yu*yu-yl*yl);
    }
    return {static_cast<double>(h*sum.area),
            {static_cast<double>(h*sum.mx),static_cast<double>(h*sum.my)}};
}

void elementary_cases() {
    const auto full=disk_cell_moments({2.1,-3.2},2.0,2,-3);
    close(full.area,1.0,0.0,"Full-cell area");
    close(full.first.x,2.0,0.0,"Full-cell global x moment");
    close(full.first.y,-3.0,0.0,"Full-cell global y moment");
    const auto outside=disk_cell_moments({2.0,0.0},0.5,0,0);
    close(outside.area,0.0,0.0,"Outside-cell area");
    close(ibdem::norm(outside.first),0.0,0.0,"Outside-cell moment");
    const auto tangent=disk_cell_moments({1.0,0.0},0.5,0,0);
    close(tangent.area,0.0,0.0,"Tangent-cell area");
    const Vec2 centre{0.19,-0.23};const double radius=0.11;
    const auto inside=disk_cell_moments(centre,radius,0,0);
    const double area=ibdem::pi*radius*radius;
    close(inside.area,area,2e-16,"Disk contained in cell area");
    close(inside.first.x,centre.x*area,2e-16,"Contained-disk x moment");
    close(inside.first.y,centre.y*area,2e-16,"Contained-disk y moment");
    // A quarter disk occupies the top-right corner of the cell. Its first
    // moments relative to the disk center are each -R^3/3.
    const double r=0.37;const auto quarter=disk_cell_moments({0.5,0.5},r,0,0);
    const double qa=ibdem::pi*r*r/4.0;
    close(quarter.area,qa,2e-16,"Quarter-disk area");
    close(quarter.first.x,0.5*qa-r*r*r/3.0,2e-16,"Quarter-disk x moment");
    close(quarter.first.y,0.5*qa-r*r*r/3.0,2e-16,"Quarter-disk y moment");
}

void total_area_and_first_moment() {
    const Vec2 centres[]={{0.0,0.0},{0.5,0.5},{0.173,-0.291},
                           {17.231,9.749},{-4.819,7.013}};
    const double radii[]={0.07,0.51,1.37,4.81,8.2};
    double worst_area=0.0,worst_first=0.0;
    for (Vec2 centre:centres) for (double radius:radii) {
        const auto sum=tile(centre,radius);
        const long double expected=std::acos(-1.0L)*radius*radius;
        const double ae=std::abs(static_cast<double>(sum.area-expected));
        const double xe=std::abs(static_cast<double>(sum.mx-centre.x*expected));
        const double ye=std::abs(static_cast<double>(sum.my-centre.y*expected));
        worst_area=std::max(worst_area,ae);worst_first=std::max({worst_first,xe,ye});
        close(static_cast<double>(sum.area-expected),0.0,2e-13*(1.0+static_cast<double>(expected)),"Tiled disk area");
        close(static_cast<double>(sum.mx-centre.x*expected),0.0,2e-13*(1.0+std::abs(centre.x)*static_cast<double>(expected)),"Tiled disk global x moment");
        close(static_cast<double>(sum.my-centre.y*expected),0.0,2e-13*(1.0+std::abs(centre.y)*static_cast<double>(expected)),"Tiled disk global y moment");
    }
    // Move through many subcell phases: the centroid must track the disk center.
    for (int k=0;k<101;++k) {
        const Vec2 centre{13.173+0.0097*k,9.291-0.0063*k};
        const auto sum=tile(centre,4.37);
        close(static_cast<double>(sum.mx/sum.area),centre.x,2e-13,"Moving disk centroid x");
        close(static_cast<double>(sum.my/sum.area),centre.y,2e-13,"Moving disk centroid y");
    }
    std::cout<<"  disk quadrature totals: max_area_error="<<worst_area
             <<" max_first_moment_error="<<worst_first<<'\n';
}

void symmetry_and_translation() {
    const Vec2 centre{0.371,-0.218};const double radius=0.63;
    const auto a=disk_cell_moments(centre,radius,0,0);
    const auto mirror=disk_cell_moments({-centre.x,centre.y},radius,0,0);
    close(mirror.area,a.area,2e-15,"Reflected area");
    close(mirror.first.x,-a.first.x,2e-15,"Reflected x moment");
    close(mirror.first.y,a.first.y,2e-15,"Reflected y moment");
    const auto rotation=disk_cell_moments({-centre.y,centre.x},radius,0,0);
    close(rotation.area,a.area,2e-15,"Rotated area");
    close(rotation.first.x,-a.first.y,2e-15,"Rotated x moment");
    close(rotation.first.y,a.first.x,2e-15,"Rotated y moment");
    const auto shift=disk_cell_moments(centre+Vec2{7,-11},radius,7,-11);
    close(shift.area,a.area,3e-15,"Integer-translated area");
    close(shift.first.x,a.first.x+7*a.area,3e-14,"Translated global x moment");
    close(shift.first.y,a.first.y-11*a.area,3e-14,"Translated global y moment");
}

void independent_numerical_integration() {
    struct Case {Vec2 centre;double radius;int x,y;};
    const Case cases[]={
        {{0.173,0.291},0.63,0,0},{{-0.42,0.09},0.21,0,0},
        {{0.2,0.2},0.1,0,0},{{1.2,0.1},0.91,0,0},
        {{0.0,0.0},0.5,0,0},{{0.9,0.9},0.75,0,0},
        {{3.37,-2.18},1.42,3,-3},{{7.23,5.79},4.37,11,7},
        {{0.499,0.499},0.002,0,0},{{-4.21,7.08},0.98,-5,7}
    };
    double worst_area=0.0,worst_local_first=0.0;
    for (const auto& c:cases) {
        const auto exact=disk_cell_moments(c.centre,c.radius,c.x,c.y);
        const auto numeric=numerical_strips(c.centre,c.radius,c.x,c.y);
        // Compare moments relative to the cell center to avoid a large global
        // coordinate obscuring the shape-dependent first-moment accuracy.
        const double ex=exact.first.x-c.x*exact.area;
        const double ey=exact.first.y-c.y*exact.area;
        const double nx=numeric.first.x-c.x*numeric.area;
        const double ny=numeric.first.y-c.y*numeric.area;
        worst_area=std::max(worst_area,std::abs(exact.area-numeric.area));
        worst_local_first=std::max({worst_local_first,std::abs(ex-nx),std::abs(ey-ny)});
        close(exact.area,numeric.area,2e-9,"Independent strip area");
        close(ex,nx,2e-9,"Independent strip x moment");
        close(ey,ny,2e-9,"Independent strip y moment");
    }
    std::cout<<"  independent 2^20-strip quadrature: max_area_error="<<worst_area
             <<" max_local_first_moment_error="<<worst_local_first<<'\n';
}

void invalid_inputs() {
    for (double r:{0.0,-1.0,std::numeric_limits<double>::quiet_NaN(),
                   std::numeric_limits<double>::infinity()}) {
        bool rejected=false;
        try { (void)disk_cell_moments({0,0},r,0,0); }
        catch (const std::invalid_argument&) {rejected=true;}
        require(rejected,"Invalid disk radius accepted");
    }
    bool rejected=false;
    try { (void)disk_cell_moments({std::numeric_limits<double>::quiet_NaN(),0},1,0,0); }
    catch (const std::invalid_argument&) {rejected=true;}
    require(rejected,"Nonfinite disk center accepted");
}
} // namespace

int run_quadrature_tests() {
    struct Test {const char* name;void (*run)();};
    const Test tests[]={
        {"Disk quadrature elementary geometry",elementary_cases},
        {"Disk quadrature exact tiled area and first moments",total_area_and_first_moment},
        {"Disk quadrature symmetry and global translation",symmetry_and_translation},
        {"Disk quadrature independent high-resolution integration",independent_numerical_integration},
        {"Disk quadrature invalid inputs",invalid_inputs}
    };
    int failures=0;
    for (const auto& t:tests) {
        try {t.run();std::cout<<"PASS "<<t.name<<'\n';}
        catch (const std::exception& e) {++failures;std::cerr<<"FAIL "<<t.name<<": "<<e.what()<<'\n';}
    }
    return failures;
}

#ifdef IBDEM_QUADRATURE_TEST_MAIN
int main() {return run_quadrature_tests();}
#endif
