"""Discrete transverse-momentum eigenmode; no fitted decay or macroscopic reset."""
import numpy as np
from body_link_extractor_v1 import C

def mode(tau,n=16):
    cy=np.array([-1,0,1]);w=np.array([1/6,2/3,1/6]);k=2*np.pi/n
    A=np.diag(np.exp(-1j*k*cy))@((1-1/tau)*np.eye(3)+np.outer(w,np.ones(3))/tau)
    vals,vecs=np.linalg.eig(A);j=np.argmin(abs(vals-1));lam=vals[j];v=vecs[:,j]/vecs[:,j].sum()
    if abs(lam.imag)>1e-12 or not 0<lam.real<1:raise ValueError('invalid shear branch')
    if np.max(abs(A@v-lam*v))>1e-12:raise ValueError('spectral residual')
    return float(lam.real),v,A

def initialize(f,tau,amplitude):
    n=f.shape[1];lam,v,A=mode(tau,n);w=np.array([1/6,2/3,1/6]);W=np.array([1/3]+[1/18]*6+[1/36]*12)
    y=np.indices((n,n,n))[1]+.5;phase=np.exp(2j*np.pi*y/n)
    coeff=3*W*C[:,0]*(v[C[:,1]+1]/w[C[:,1]+1]-1)
    correction=amplitude*np.imag(coeff[:,None,None,None]*phase)
    if np.max(abs(correction.sum(axis=0)))>1e-14 or np.max(abs(C.T@correction.reshape(19,-1)))>1e-14:raise ValueError('changed initial moments')
    return f+correction
