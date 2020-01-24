from abc import ABCMeta, abstractmethod
from collections import namedtuple
import math

from funcsigs import signature
import warnings

import numpy as np
from scipy.special import kv, gamma
from scipy.spatial.distance import pdist, cdist, squareform

#from ..metrics.pairwise import pairwise_kernels
#from ..base import clone
#from ..utils.validation import _num_samples
from sklearn.gaussian_process import *

from sklearn.gaussian_process.kernels import StationaryKernelMixin, NormalizedKernelMixin, Kernel


class RBF_Sep(StationaryKernelMixin, NormalizedKernelMixin, Kernel):
    """Radial-basis function kernel (aka squared-exponential kernel).
    The RBF kernel is a stationary kernel. It is also known as the
    "squared exponential" kernel. It is parameterized by a length-scale
    parameter length_scale>0, which can either be a scalar (isotropic variant
    of the kernel) or a vector with the same number of dimensions as the inputs
    X (anisotropic variant of the kernel). The kernel is given by:
    k(x_i, x_j) = exp(-1 / 2 d(x_i / length_scale, x_j / length_scale)^2)
    This kernel is infinitely differentiable, which implies that GPs with this
    kernel as covariance function have mean square derivatives of all orders,
    and are thus very smooth.
    .. versionadded:: 0.18
    Parameters
    ----------
    length_scale : float or array with shape (n_features,), default: 1.0
        The length scale of the kernel. If a float, an isotropic kernel is
        used. If an array, an anisotropic kernel is used where each dimension
        of l defines the length-scale of the respective feature dimension.
    length_scale_bounds : pair of floats >= 0, default: (1e-5, 1e5)
        The lower and upper bound on length_scale
    """
    def __init__(self, length_scale=1.0, t_length_scale=1.0, length_scale_bounds=(1e-5, 1e5)):
        self.length_scale = length_scale
        self.length_scale_bounds = length_scale_bounds
        self.t_length_scale = t_length_scale

    @property
    def anisotropic(self):
        return np.iterable(self.length_scale) and len(self.length_scale) > 1

    @property
    def hyperparameter_length_scale(self):
        if self.anisotropic:
            return Hyperparameter("length_scale", "numeric",
                                  self.length_scale_bounds,
                                  len(self.length_scale))
        return Hyperparameter(
            "length_scale", "numeric", self.length_scale_bounds)

    def __call__(self, X, Y=None, eval_gradient=False):
        """Return the kernel k(X, Y) and optionally its gradient.
        Parameters
        ----------
        X : array, shape (n_samples_X, n_features)
            Left argument of the returned kernel k(X, Y)
        Y : array, shape (n_samples_Y, n_features), (optional, default=None)
            Right argument of the returned kernel k(X, Y). If None, k(X, X)
            if evaluated instead.
        eval_gradient : bool (optional, default=False)
            Determines whether the gradient with respect to the kernel
            hyperparameter is determined. Only supported when Y is None.
        Returns
        -------
        K : array, shape (n_samples_X, n_samples_Y)
            Kernel k(X, Y)
        K_gradient : array (opt.), shape (n_samples_X, n_samples_X, n_dims)
            The gradient of the kernel k(X, X) with respect to the
            hyperparameter of the kernel. Only returned when eval_gradient
            is True.
        """
        X = np.atleast_2d(X)
        length_scale = _check_length_scale(X, self.length_scale)

########### MODIFICATION

# TODO separate lengthscales 

        X_1 = X[:,:-1]
        X_t = X[:, -1]
        Y_1 = Y[:,:-1]
        Y_t = Y[:, -1]

        if Y is None:
            dists1 = pdist(X_1 / length_scale, metric='sqeuclidean')
            K1 = np.exp(-.5 * dists)
            # convert from upper-triangular matrix to square matrix
            K1 = squareform(K1)
            np.fill_diagonal(K1, 1)

            dists2 = pdist(X_t / length_scale, metric='sqeuclidean')
            K2 = np.exp(-.5 * dists)
            # convert from upper-triangular matrix to square matrix
            K2 = squareform(K2)
            np.fill_diagonal(K2, 1)

            K = np.matmul(K1, K2)
        else:
            if eval_gradient:
                raise ValueError(
                    "Gradient can only be evaluated when Y is None.")
            dists1 = cdist(X_1 / length_scale, Y_1 / length_scale,
                          metric='sqeuclidean')
            K1 = np.exp(-.5 * dists1)
            dists2 = cdist(X_t / length_scale, Y_t / length_scale,
                          metric='sqeuclidean')
            K2 = np.exp(-.5 * dists2)

            K = np.matmul(K1, K2)

##########

        if eval_gradient:
            if self.hyperparameter_length_scale.fixed:
                # Hyperparameter l kept fixed
                return K, np.empty((X.shape[0], X.shape[0], 0))
            elif not self.anisotropic or length_scale.shape[0] == 1:
                K_gradient = \
                    (K * squareform(dists))[:, :, np.newaxis]
                return K, K_gradient
            elif self.anisotropic:
                # We need to recompute the pairwise dimension-wise distances
                K_gradient = (X[:, np.newaxis, :] - X[np.newaxis, :, :]) ** 2 \
                    / (length_scale ** 2)
                K_gradient *= K[..., np.newaxis]
                return K, K_gradient
        else:
            return K

    def __repr__(self):
        if self.anisotropic:
            return "{0}(length_scale=[{1}])".format(
                self.__class__.__name__, ", ".join(map("{0:.3g}".format,
                                                   self.length_scale)))
        else:  # isotropic
            return "{0}(length_scale={1:.3g})".format(
                self.__class__.__name__, np.ravel(self.length_scale)[0])



if __name__ == "__main__":
    rbf = RBF_Sep(1.0)