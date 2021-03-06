
# Copyright (c) 2015, 2014 Computational Molecular Biology Group, Free University
# Berlin, 14195 Berlin, Germany.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

r"""This module provides matrix-decomposition based functions for the
analysis of stochastic matrices

Below are the dense implementations for functions specified in msm.api. 
Dense matrices are represented by numpy.ndarrays throughout this module.

.. moduleauthor:: B.Trendelkamp-Schroer <benjamin DOT trendelkamp-schroer AT fu-berlin DOT de>

"""

import numpy as np
import numbers
import warnings

from scipy.linalg import eig, eigh, eigvals, eigvalsh, solve, lu_factor, lu_solve
from msmtools.util.exceptions import SpectralWarning, ImaginaryEigenValueWarning


def backward_iteration(A, mu, x0, tol=1e-14, maxiter=100):
    r"""Find eigenvector to approximate eigenvalue via backward iteration.

    Parameters
    ----------
    A : (N, N) ndarray
        Matrix for which eigenvector is desired
    mu : float
        Approximate eigenvalue for desired eigenvector
    x0 : (N, ) ndarray
        Initial guess for eigenvector
    tol : float
        Tolerace parameter for termination of iteration

    Returns
    -------
    x : (N, ) ndarray
        Eigenvector to approximate eigenvalue mu

    """
    T = A - mu * np.eye(A.shape[0])
    """LU-factor of T"""
    lupiv = lu_factor(T)
    """Starting iterate with ||y_0||=1"""
    r0 = 1.0 / np.linalg.norm(x0)
    y0 = x0 * r0
    """Local variables for inverse iteration"""
    y = 1.0 * y0
    r = 1.0 * r0
    for i in range(maxiter):
        x = lu_solve(lupiv, y)
        r = 1.0 / np.linalg.norm(x)
        y = x * r
        if r <= tol:
            return y
    msg = "Failed to converge after %d iterations, residuum is %e" % (maxiter, r)
    raise RuntimeError(msg)


def stationary_distribution_from_backward_iteration(P, eps=1e-15):
    r"""Fast computation of the stationary vector using backward
    iteration.

    Parameters
    ----------
    P : (M, M) ndarray
        Transition matrix
    eps : float (optional)
        Perturbation parameter for the true eigenvalue.
        
    Returns
    -------
    pi : (M,) ndarray
        Stationary vector

    """
    A = np.transpose(P)
    mu = 1.0 - eps
    x0 = np.ones(P.shape[0])
    y = backward_iteration(A, mu, x0)
    pi = y / y.sum()
    return pi


def stationary_distribution_from_eigenvector(T):
    r"""Compute stationary distribution of stochastic matrix T. 

    The stationary distribution is the left eigenvector corresponding to the 
    non-degenerate eigenvalue :math: `\lambda=1`.

    Input:
    ------
    T : numpy array, shape(d,d)
        Transition matrix (stochastic matrix).

    Returns
    -------
    mu : numpy array, shape(d,)
        Vector of stationary probabilities.

    """
    val, L = eig(T, left=True, right=False)

    """ Sorted eigenvalues and left and right eigenvectors. """
    perm = np.argsort(val)[::-1]

    val = val[perm]
    L = L[:, perm]
    """ Make sure that stationary distribution is non-negative and l1-normalized """
    nu = np.abs(L[:, 0])
    mu = nu / np.sum(nu)
    return mu


def eigenvalues(T, k=None, reversible=False, mu=None):
    r"""Compute eigenvalues of given transition matrix.
    
    Eigenvalues are computed using the numpy.linalg interface 
    for the corresponding LAPACK routines.    

    Input
    -----
    T : numpy.ndarray, shape=(d,d)
        Transition matrix (stochastic matrix).
    k : int (optional) or tuple of ints
        Compute the first k eigenvalues of T.
    reversible : bool (optional)
        Indicate that transition matrix is reversible. Will compute its stationary distribution `\mu` (unless given)
        and then compute the eigenvalues of the symmetric matrix `\sqrt(\mu_i / \mu_j)` which is equivalent but
        much faster
    mu : numpy.ndarray, shape=(d)
        Stationary distribution of T. Will only be used if reversible=True in order to symmetrize T.

    Returns
    -------
    eig : numpy.ndarray, shape(n,)
        The eigenvalues of T ordered with decreasing absolute value.
        If k is None then n=d, if k is int then n=k otherwise
        n is the length of the given tuple of eigenvalue indices.

    """
    if reversible:
        # compute stationary distribution if not given
        if mu is None:
            mu = stationary_distribution_from_backward_iteration(T)
        # symmetrize T
        smu = np.sqrt(mu)
        S = smu[:,None] * T / smu
        # symmetric eigenvalue problem
        evals = eigvalsh(S)
    else:
        evals = eigvals(T)

    """Sort by decreasing absolute value"""
    ind = np.argsort(np.abs(evals))[::-1]
    evals = evals[ind]

    if isinstance(k, (list, set, tuple)):
        try:
            return [evals[n] for n in k]
        except IndexError:
            raise ValueError("given indices do not exist: ", k)
    elif k is not None:
        return evals[: k]
    else:
        return evals


def eigenvectors(T, k=None, right=True):
    r"""Compute eigenvectors of given transition matrix.

    Eigenvectors are computed using the numpy.linalg interface 
    for the corresponding LAPACK routines.    

    Input
    -----
    T : numpy.ndarray, shape(d,d)
        Transition matrix (stochastic matrix).
    k : int (optional) or tuple of ints
        Compute the first k eigenvalues of T.

    Returns
    -------
    eigvec : numpy.ndarray, shape=(d, n)
        The eigenvectors of T ordered with decreasing absolute value of
        the corresponding eigenvalue. If k is None then n=d, if k is\
        int then n=k otherwise n is the length of the given tuple of\
        eigenvector indices.

    """
    if right:
        val, R = eig(T, left=False, right=True)
        """ Sorted eigenvalues and left and right eigenvectors. """
        perm = np.argsort(np.abs(val))[::-1]

        # eigval=val[perm]
        eigvec = R[:, perm]

    else:
        val, L = eig(T, left=True, right=False)

        """ Sorted eigenvalues and left and right eigenvectors. """
        perm = np.argsort(np.abs(val))[::-1]

        # eigval=val[perm]
        eigvec = L[:, perm]

    """ Return eigenvectors """
    if k is None:
        return eigvec
    elif isinstance(k, numbers.Integral):
        return eigvec[:, 0:k]
    else:
        ind = np.asarray(k)
        return eigvec[:, ind]


def rdl_decomposition(T, k=None, norm='standard'):
    r"""Compute the decomposition into left and right eigenvectors.
    
    Parameters
    ----------
    T : (M, M) ndarray 
        Transition matrix    
    k : int (optional)
        Number of eigenvector/eigenvalue pairs
    norm: {'standard', 'reversible'}
        standard: (L'R) = Id, L[:,0] is a probability distribution,
            the stationary distribution mu of T. Right eigenvectors
            R have a 2-norm of 1.
        reversible: R and L are related via L=L[:,0]*R.
        auto: will be reversible if T is reversible, otherwise standard.

    Returns
    -------
    R : (M, M) ndarray
        The normalized (with respect to L) right eigenvectors, such that the 
        column R[:,i] is the right eigenvector corresponding to the eigenvalue 
        w[i], dot(T,R[:,i])=w[i]*R[:,i]
    D : (M, M) ndarray
        A diagonal matrix containing the eigenvalues, each repeated
        according to its multiplicity
    L : (M, M) ndarray
        The normalized (with respect to `R`) left eigenvectors, such that the 
        row ``L[i, :]`` is the left eigenvector corresponding to the eigenvalue
        ``w[i]``, ``dot(L[i, :], T)``=``w[i]*L[i, :]``
        
    """
    d = T.shape[0]
    w, R = eig(T)

    """Sort by decreasing magnitude of eigenvalue"""
    ind = np.argsort(np.abs(w))[::-1]
    w = w[ind]
    R = R[:, ind]

    """Diagonal matrix containing eigenvalues"""
    D = np.diag(w)

    # auto-set norm
    if norm == 'auto':
        from msmtools.analysis import is_reversible

        if (is_reversible(T)):
            norm = 'reversible'
        else:
            norm = 'standard'
    # Standard norm: Euclidean norm is 1 for r and LR = I.
    if norm == 'standard':
        L = solve(np.transpose(R), np.eye(d))

        """l1- normalization of L[:, 0]"""
        R[:, 0] = R[:, 0] * np.sum(L[:, 0])
        L[:, 0] = L[:, 0] / np.sum(L[:, 0])

        if k is None:
            return R, D, np.transpose(L)
        else:
            return R[:, 0:k], D[0:k, 0:k], np.transpose(L[:, 0:k])

    # Reversible norm:
    elif norm == 'reversible':
        b = np.zeros(d)
        b[0] = 1.0

        A = np.transpose(R)
        nu = solve(A, b)
        mu = nu / np.sum(nu)

        """Ensure that R[:,0] is positive"""
        R[:, 0] = R[:, 0] / np.sign(R[0, 0])

        """Use mu to connect L and R"""
        L = mu[:, np.newaxis] * R

        """Compute overlap"""
        s = np.diag(np.dot(np.transpose(L), R))

        """Renormalize left-and right eigenvectors to ensure L'R=Id"""
        R = R / np.sqrt(s[np.newaxis, :])
        L = L / np.sqrt(s[np.newaxis, :])

        if k is None:
            return R, D, np.transpose(L)
        else:
            return R[:, 0:k], D[0:k, 0:k], np.transpose(L[:, 0:k])
    else:
        raise ValueError("Keyword 'norm' has to be either 'standard' or 'reversible'")


def timescales(T, tau=1, k=None, reversible=False, mu=None):
    r"""Compute implied time scales of given transition matrix
    
    Parameters
    ----------
    T : transition matrix
    tau : lag time
    k : int (optional)
        Compute the first k implied time scales.
    reversible : bool (optional)
        Indicate that transition matrix is reversible. Will compute its stationary distribution `\mu` (unless given)
        and then compute the eigenvalues of the symmetric matrix `\sqrt(\mu_i / \mu_j)` which is equivalent but
        much faster
    mu : numpy.ndarray, shape=(d)
        Stationary distribution of T. Will only be used if reversible=True in order to symmetrize T.

    Returns
    -------
    ts : ndarray
        The implied time scales of the transition matrix.          
    
    """
    values = eigenvalues(T, reversible=reversible, mu=mu)

    """Sort by absolute value"""
    ind = np.argsort(np.abs(values))[::-1]
    values = values[ind]

    if k is None:
        values = values
    else:
        values = values[0:k]

    """Compute implied time scales"""
    return timescales_from_eigenvalues(values, tau)


def timescales_from_eigenvalues(evals, tau=1):
    r"""Compute implied time scales from given eigenvalues
    
    Parameters
    ----------
    evals : eigenvalues
    tau : lag time

    Returns
    -------
    ts : ndarray
        The implied time scales to the given eigenvalues, in the same order.
    
    """

    """Check for dominant eigenvalues with large imaginary part"""

    if not np.allclose(evals.imag, 0.0):
        warnings.warn('Using eigenvalues with non-zero imaginary part', ImaginaryEigenValueWarning)

    """Check for multiple eigenvalues of magnitude one"""
    ind_abs_one = np.isclose(np.abs(evals), 1.0, rtol=0.0, atol=1e-14)
    if sum(ind_abs_one) > 1:
        warnings.warn('Multiple eigenvalues with magnitude one.', SpectralWarning)

    """Compute implied time scales"""
    ts = np.zeros(len(evals))

    """Eigenvalues of magnitude one imply infinite timescale"""
    ts[ind_abs_one] = np.inf

    """All other eigenvalues give rise to finite timescales"""
    ts[np.logical_not(ind_abs_one)] = \
        -1.0 * tau / np.log(np.abs(evals[np.logical_not(ind_abs_one)]))
    return ts
    
