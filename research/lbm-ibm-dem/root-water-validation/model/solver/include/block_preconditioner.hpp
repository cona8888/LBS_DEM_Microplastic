#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace ibdem {

// Inverse application for A=(G tensor I_2)+U*D without constructing A or an
// explicit inverse. Marker components are interleaved [x0,y0,x1,y1,...].
// G is row-major n*n, U is row-major (2*n)*rank, D is row-major rank*(2*n).
// G must be symmetric positive definite. D need not equal U^T, so the small
// Woodbury matrix is factored by pivoted LU, not by Cholesky.
//
// Setup: L L^T=G; Y=(G^-1 tensor I_2) U; Z=I+D Y.
// Apply: p=(G^-1 tensor I_2)v; w=Z^-1 Dp; result=p-Yw.
// No regularization or diagonal jitter changes the supplied block. Invalid or
// numerically singular blocks throw; the caller may select another preconditioner.
class StructuredBlockPreconditioner {
public:
    StructuredBlockPreconditioner()=default;

    StructuredBlockPreconditioner(const std::vector<double>& G, int n,
                                  const std::vector<double>& U,
                                  const std::vector<double>& D, int rank) {
        setup(G,n,U,D,rank);
    }

    void setup(const std::vector<double>& G, int n,
               const std::vector<double>& U,
               const std::vector<double>& D, int rank) {
        if (n<0 || rank<0)
            throw std::invalid_argument("Structured block: negative marker count or rank");
        const std::size_t nn=static_cast<std::size_t>(n);
        const std::size_t rr=static_cast<std::size_t>(rank);
        const std::size_t m=product(nn,2);
        if (G.size()!=product(nn,nn) || U.size()!=product(m,rr) ||
            D.size()!=product(rr,m))
            throw std::invalid_argument("Structured block: inconsistent G/U/D dimensions");
        requireFinite(G,"Structured block: nonfinite G");
        requireFinite(U,"Structured block: nonfinite U");
        requireFinite(D,"Structured block: nonfinite D");

        // Build in local storage: a failed rebuild leaves an existing valid
        // preconditioner intact, rather than leaving partially factored data.
        std::vector<double> L(product(nn,nn),0.0);
        double g_scale=0.0;
        for (double x:G) g_scale=std::max(g_scale,std::abs(x));
        const double symmetry_tolerance=128*std::numeric_limits<double>::epsilon()*g_scale;
        for (std::size_t i=0;i<nn;++i) {
            for (std::size_t j=0;j<i;++j) {
                if (std::abs(G[i*nn+j]-G[j*nn+i])>symmetry_tolerance)
                    throw std::invalid_argument("Structured block: G is not symmetric to roundoff");
            }
        }
        for (std::size_t i=0;i<nn;++i) {
            for (std::size_t j=0;j<=i;++j) {
                // The lower triangle is authoritative after the symmetry test.
                double value=G[i*nn+j];
                for (std::size_t k=0;k<j;++k)
                    value-=L[i*nn+k]*L[j*nn+k];
                if (!std::isfinite(value))
                    throw std::runtime_error("Structured block: nonfinite Cholesky update");
                if (i==j) {
                    if (!(value>0.0))
                        throw std::runtime_error("Structured block: G is not positive definite");
                    L[i*nn+j]=std::sqrt(value);
                } else {
                    L[i*nn+j]=value/L[j*nn+j];
                    if (!std::isfinite(L[i*nn+j]))
                        throw std::runtime_error("Structured block: nonfinite Cholesky factor");
                }
            }
        }

        std::vector<double> Y=U;
        std::vector<double> stored_D=D;
        if (rr>0) {
            // The same storage is n rows with 2*rank right-hand sides: x's
            // rank columns followed by y's rank columns for each marker.
            solveG(L,nn,Y,product(2,rr));
        }
        std::vector<double> Z(product(rr,rr),0.0);
        for (std::size_t i=0;i<rr;++i) {
            for (std::size_t j=0;j<rr;++j) {
                double value=i==j ? 1.0 : 0.0;
                for (std::size_t k=0;k<m;++k)
                    value+=D[i*m+k]*Y[k*rr+j];
                Z[i*rr+j]=value;
            }
        }
        requireFinite(Z,"Structured block: nonfinite Woodbury matrix");
        std::vector<std::size_t> pivots(rr);
        factorLU(Z,rr,pivots);

        n_=nn;
        rank_=rr;
        L_=std::move(L);
        Y_=std::move(Y);
        D_=std::move(stored_D);
        Z_lu_=std::move(Z);
        pivots_=std::move(pivots);
        ready_=true;
    }

    std::vector<double> apply(const std::vector<double>& v) const {
        std::vector<double> result=v;
        applyInPlace(result);
        return result;
    }

    void applyInPlace(std::vector<double>& v) const {
        if (!ready_)
            throw std::logic_error("Structured block: setup must precede apply");
        const std::size_t m=2*n_;
        if (v.size()!=m)
            throw std::invalid_argument("Structured block: wrong right-hand-side dimension");
        requireFinite(v,"Structured block: nonfinite right-hand side");
        solveG(L_,n_,v,2);
        if (rank_==0) return;
        std::vector<double> w(rank_,0.0);
        for (std::size_t i=0;i<rank_;++i) {
            double value=0.0;
            for (std::size_t j=0;j<m;++j) value+=D_[i*m+j]*v[j];
            w[i]=value;
        }
        solveLU(Z_lu_,rank_,pivots_,w);
        for (std::size_t i=0;i<m;++i) {
            double correction=0.0;
            for (std::size_t j=0;j<rank_;++j)
                correction+=Y_[i*rank_+j]*w[j];
            v[i]-=correction;
        }
        requireFinite(v,"Structured block: nonfinite inverse application");
    }

    std::size_t markerCount() const { return n_; }
    std::size_t rank() const { return rank_; }
    bool ready() const { return ready_; }

private:
    std::size_t n_=0, rank_=0;
    bool ready_=false;
    std::vector<double> L_,Y_,D_,Z_lu_;
    std::vector<std::size_t> pivots_;

    static std::size_t product(std::size_t a,std::size_t b) {
        if (b!=0 && a>std::numeric_limits<std::size_t>::max()/b)
            throw std::invalid_argument("Structured block: matrix dimension overflow");
        return a*b;
    }

    static void requireFinite(const std::vector<double>& a,const char* message) {
        for (double x:a) if (!std::isfinite(x)) throw std::runtime_error(message);
    }

    // In-place solve of G X=B, B stored row-major n*nrhs. Sharing each L entry
    // across all RHS columns avoids separate x/y and rank-column factorizations.
    static void solveG(const std::vector<double>& L,std::size_t n,
                       std::vector<double>& B,std::size_t nrhs) {
        for (std::size_t i=0;i<n;++i) {
            double* row=B.data()+i*nrhs;
            for (std::size_t j=0;j<i;++j) {
                const double l=L[i*n+j];
                const double* previous=B.data()+j*nrhs;
                for (std::size_t k=0;k<nrhs;++k) row[k]-=l*previous[k];
            }
            for (std::size_t k=0;k<nrhs;++k) row[k]/=L[i*n+i];
        }
        for (std::size_t i=n;i-- >0;) {
            double* row=B.data()+i*nrhs;
            for (std::size_t j=i+1;j<n;++j) {
                const double l=L[j*n+i];
                const double* following=B.data()+j*nrhs;
                for (std::size_t k=0;k<nrhs;++k) row[k]-=l*following[k];
            }
            for (std::size_t k=0;k<nrhs;++k) row[k]/=L[i*n+i];
        }
        requireFinite(B,"Structured block: nonfinite triangular solve");
    }

    static void factorLU(std::vector<double>& a,std::size_t n,
                         std::vector<std::size_t>& pivots) {
        double scale=0.0;
        for (double x:a) scale=std::max(scale,std::abs(x));
        const double tolerance=64*std::numeric_limits<double>::epsilon()*scale*std::max<std::size_t>(1,n);
        for (std::size_t k=0;k<n;++k) {
            std::size_t pivot=k;
            for (std::size_t i=k+1;i<n;++i)
                if (std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
            if (!(std::abs(a[pivot*n+k])>tolerance) || !std::isfinite(a[pivot*n+k]))
                throw std::runtime_error("Structured block: singular or numerically singular Woodbury matrix");
            pivots[k]=pivot;
            if (pivot!=k)
                for (std::size_t j=0;j<n;++j) std::swap(a[k*n+j],a[pivot*n+j]);
            for (std::size_t i=k+1;i<n;++i) {
                a[i*n+k]/=a[k*n+k];
                for (std::size_t j=k+1;j<n;++j)
                    a[i*n+j]-=a[i*n+k]*a[k*n+j];
            }
        }
        requireFinite(a,"Structured block: nonfinite Woodbury LU factor");
    }

    static void solveLU(const std::vector<double>& a,std::size_t n,
                        const std::vector<std::size_t>& pivots,
                        std::vector<double>& b) {
        requireFinite(b,"Structured block: nonfinite Woodbury right-hand side");
        // Apply every stored row permutation before solving with the final L.
        for (std::size_t i=0;i<n;++i)
            if (pivots[i]!=i) std::swap(b[i],b[pivots[i]]);
        for (std::size_t i=0;i<n;++i)
            for (std::size_t j=0;j<i;++j) b[i]-=a[i*n+j]*b[j];
        for (std::size_t i=n;i-- >0;) {
            for (std::size_t j=i+1;j<n;++j) b[i]-=a[i*n+j]*b[j];
            b[i]/=a[i*n+i];
        }
        requireFinite(b,"Structured block: nonfinite Woodbury solve");
    }
};

} // namespace ibdem
