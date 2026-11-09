#include "block_preconditioner.hpp"
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>

namespace {

// Independent direct solve of the explicitly assembled full matrix. This uses
// Gaussian elimination on A and b together, not the structured factorization.
std::vector<double> denseSolve(std::vector<double> a,std::vector<double> b) {
    const std::size_t n=b.size();
    for (std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for (std::size_t i=k+1;i<n;++i)
            if (std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
        if (!(std::abs(a[pivot*n+k])>0)) throw std::runtime_error("Singular dense test matrix");
        for (std::size_t j=0;j<n;++j) std::swap(a[k*n+j],a[pivot*n+j]);
        std::swap(b[k],b[pivot]);
        for (std::size_t i=k+1;i<n;++i) {
            const double factor=a[i*n+k]/a[k*n+k];
            a[i*n+k]=0;
            for (std::size_t j=k+1;j<n;++j) a[i*n+j]-=factor*a[k*n+j];
            b[i]-=factor*b[k];
        }
    }
    for (std::size_t i=n;i-- >0;) {
        for (std::size_t j=i+1;j<n;++j) b[i]-=a[i*n+j]*b[j];
        b[i]/=a[i*n+i];
    }
    return b;
}

std::vector<double> fullMatrix(const std::vector<double>& g,int n,
                               const std::vector<double>& u,
                               const std::vector<double>& d,int rank) {
    const int m=2*n;
    std::vector<double> a(m*m,0);
    for (int i=0;i<m;++i) for (int j=0;j<m;++j) {
        if (i%2==j%2) a[i*m+j]=g[(i/2)*n+j/2];
        for (int k=0;k<rank;++k) a[i*m+j]+=u[i*rank+k]*d[k*m+j];
    }
    return a;
}

template<class F> bool throws(F&& f) {
    try { f(); } catch (const std::exception&) { return true; }
    return false;
}

} // namespace

int run_block_tests() {
    using ibdem::StructuredBlockPreconditioner;
    int failures=0;
    std::cout<<std::setprecision(17);
    const auto report=[&](const std::string& name,bool ok,const std::string& detail) {
        std::cout<<"TEST "<<name<<" "<<(ok?"PASS":"FAIL")<<" "<<detail<<"\n";
        failures+=!ok;
    };
    const auto number=[](double x) { std::ostringstream s; s<<std::setprecision(17)<<x; return s.str(); };

    try {
        std::mt19937 engine(49103);
        std::uniform_real_distribution<double> uniform(-1,1);
        double worst_error=0,worst_residual=0;
        int cases=0;
        for (int n : {1,3,8,17}) for (int rank : {0,1,3,6}) {
            const int m=2*n;
            std::vector<double> h(n*n),g(n*n,0),u(m*rank),d(rank*m),rhs(m);
            for (double& v:h) v=uniform(engine);
            for (int i=0;i<n;++i) for (int j=0;j<n;++j) {
                g[i*n+j]=i==j ? 1.5 : 0.0;
                for (int k=0;k<n;++k) g[i*n+j]+=h[i*n+k]*h[j*n+k];
            }
            for (double& v:u) v=0.2*uniform(engine);
            for (double& v:d) v=0.2*uniform(engine);
            StructuredBlockPreconditioner p(g,n,u,d,rank);
            const auto a=fullMatrix(g,n,u,d,rank);
            for (int repeat=0;repeat<3;++repeat) {
                for (double& v:rhs) v=uniform(engine);
                const auto x=p.apply(rhs);
                const auto exact=denseSolve(a,rhs);
                double scale=1,residual_scale=1;
                for (double v:exact) scale=std::max(scale,std::abs(v));
                for (double v:rhs) residual_scale=std::max(residual_scale,std::abs(v));
                for (int i=0;i<m;++i) {
                    worst_error=std::max(worst_error,std::abs(x[i]-exact[i])/scale);
                    double residual=-rhs[i];
                    for (int j=0;j<m;++j) residual+=a[i*m+j]*x[j];
                    worst_residual=std::max(worst_residual,std::abs(residual)/residual_scale);
                }
                ++cases;
            }
        }
        report("block_dense_reference",worst_error<1e-10 && worst_residual<1e-10,
               "rhs_cases="+std::to_string(cases)+" max_relative_error="+number(worst_error)+" max_scaled_residual="+number(worst_residual));
    } catch (const std::exception& e) { report("block_dense_reference",false,std::string("exception=")+e.what()); }

    try {
        // Here A=Z=[[0,2],[1,3]], so the small factorization must pivot.
        StructuredBlockPreconditioner p({1},1,{1,0,0,1},{-1,2,1,2},2);
        const auto x=p.apply({4,7});
        const double error=std::max(std::abs(x[0]-1),std::abs(x[1]-2));
        report("block_pivoted_correction",error<1e-12,"max_error="+number(error));
    } catch (const std::exception& e) { report("block_pivoted_correction",false,std::string("exception=")+e.what()); }

    try {
        // Known solution distinguishes x/y interleaving and rank-zero handling.
        const std::vector<double> g={4,1,0,1,3,0.5,0,0.5,2};
        StructuredBlockPreconditioner p(g,3,{}, {},0);
        const std::vector<double> expected={1,7,-2,3,0.5,-4};
        std::vector<double> rhs(6,0);
        for (int i=0;i<3;++i) for (int j=0;j<3;++j)
            for (int c=0;c<2;++c) rhs[2*i+c]+=g[3*i+j]*expected[2*j+c];
        p.applyInPlace(rhs);
        double error=0;
        for (int i=0;i<6;++i) error=std::max(error,std::abs(rhs[i]-expected[i]));
        StructuredBlockPreconditioner empty({},0,{}, {},0);
        report("block_rank_zero_interleaving",error<1e-12 && empty.apply({}).empty(),"max_error="+number(error));
    } catch (const std::exception& e) { report("block_rank_zero_interleaving",false,std::string("exception=")+e.what()); }

    try {
        const double nan=std::numeric_limits<double>::quiet_NaN();
        int guarded=0;
        guarded+=throws([] { StructuredBlockPreconditioner p({1,2,2,1},2,{}, {},0); }); // indefinite
        guarded+=throws([] { StructuredBlockPreconditioner p({1,1,1,1},2,{}, {},0); }); // semidefinite
        guarded+=throws([] { StructuredBlockPreconditioner p({2,1,0,2},2,{}, {},0); }); // nonsymmetric
        guarded+=throws([] { StructuredBlockPreconditioner p({1},1,{1}, {},1); }); // bad dimensions
        guarded+=throws([&] { StructuredBlockPreconditioner p({nan},1,{}, {},0); });
        guarded+=throws([] { StructuredBlockPreconditioner p({1},1,{1,0},{-1,0},1); }); // singular Z
        guarded+=throws([] { StructuredBlockPreconditioner p; p.apply({}); });
        StructuredBlockPreconditioner p({2},1,{}, {},0);
        guarded+=throws([&] { p.apply({nan,0}); });
        guarded+=throws([&] { p.apply({1}); });
        guarded+=throws([&] { p.setup({-1},1,{}, {},0); });
        const auto preserved=p.apply({2,4});
        const bool retained=std::abs(preserved[0]-1)<1e-14 && std::abs(preserved[1]-2)<1e-14;
        report("block_input_guards",guarded==10 && retained,
               "rejected_cases="+std::to_string(guarded)+" previous_setup_preserved="+std::to_string(retained));
    } catch (const std::exception& e) { report("block_input_guards",false,std::string("exception=")+e.what()); }
    return failures;
}
