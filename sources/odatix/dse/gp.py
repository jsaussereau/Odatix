# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
A Gaussian process, only as much of one as an inner loop of a search needs.

:mod:`odatix.dse.bayesian` fits one of these per objective: a handful of
points -- an evaluation is an hour of synthesis, so a campaign never has many
-- refit after every design that comes back. What is here is deliberately
small next to what a dedicated GP library offers: one kernel, a zero mean over
standardized outputs, and a marginal likelihood fit with a few random
restarts, which is what the size of archive this ever sees calls for.
"""

import numpy as np
from scipy.optimize import minimize

__all__ = ["GaussianProcess"]

#: Added to the diagonal of the kernel matrix so that two points close enough
#: to be numerically identical still leave it invertible.
_JITTER = 1e-8


def _sq_dist(a, b):
    """The squared Euclidean distance between every row of ``a`` and ``b``."""
    return (
        np.sum(a ** 2, axis=1)[:, None]
        + np.sum(b ** 2, axis=1)[None, :]
        - 2.0 * a.dot(b.T)
    )


class GaussianProcess(object):
    """
    A zero-mean GP over inputs already scaled to ``[0, 1]`` per axis, with an
    ARD squared-exponential kernel: one length scale per input dimension, so
    an axis an objective does not care about is free to flatten out on its
    own rather than the search having to tell the model which axes matter.

    Args:
        restarts (int): how many random starting points the marginal
            likelihood is optimized from. A GP fit on a dozen points has a
            likelihood surface with real local optima, and refitting from
            scratch after every design is cheap next to the synthesis that
            produced it -- there is no reason to settle for the first one.
        seed: what makes a fit repeatable. A campaign hands each objective's
            model a seed drawn from its own random source, so a search given
            a seed still runs the same way twice.
    """

    def __init__(self, restarts=3, seed=None):
        self.restarts = max(1, int(restarts))
        self.rng = np.random.RandomState(seed)
        self.X = None
        self.y_mean = 0.0
        self.y_std = 1.0
        self.length_scales = None
        self.signal_var = 1.0
        self.noise_var = 1e-4
        self._L = None
        self._alpha = None

    @property
    def fitted(self):
        return self.X is not None

    def fit(self, X, y):
        """
        Fit the kernel's hyperparameters, and what they condition on.

        Args:
            X (array-like): inputs, already normalized to ``[0, 1]`` per axis.
            y (array-like): one number per input, on its own scale -- what is
                fit against is standardized here, so an objective in the
                thousands and one between zero and one are equally easy to
                model.

        Returns:
            GaussianProcess: itself, so a fit can be chained onto a
            construction.
        """
        X = np.atleast_2d(np.asarray(X, dtype=float))
        y = np.asarray(y, dtype=float).reshape(-1)
        dims = X.shape[1]

        self.y_mean = float(np.mean(y))
        self.y_std = float(np.std(y)) or 1.0
        target = (y - self.y_mean) / self.y_std

        # Bounded in log-space, generously but not without limit: an
        # unconstrained fit on a handful of points can walk a length scale or
        # a signal variance out to where its exponential overflows, chasing a
        # marginal likelihood that keeps improving only because the surface
        # it is climbing has stopped being one a float can represent.
        bounds = (
            [(np.log(1e-3), np.log(1e2))] * dims
            + [(np.log(1e-3), np.log(1e6))]
            + [(np.log(1e-8), np.log(1.0))]
        )

        best = None
        for _ in range(self.restarts):
            start = np.concatenate((
                np.log(self.rng.uniform(0.1, 1.0, size=dims)),
                [np.log(self.rng.uniform(0.5, 2.0))],
                [np.log(self.rng.uniform(1e-4, 1e-2))],
            ))
            result = minimize(
                self._negative_log_likelihood, start, args=(X, target),
                method="L-BFGS-B", bounds=bounds,
            )
            # The very first attempt is kept even when it did not converge --
            # a fit is not worth crashing a search over -- and only replaced
            # by one both successful and better.
            if best is None or (result.success and result.fun < best.fun):
                best = result

        dims_slice, signal_index, noise_index = slice(0, dims), dims, dims + 1
        self.length_scales = np.exp(best.x[dims_slice])
        self.signal_var = float(np.exp(best.x[signal_index]))
        self.noise_var = float(np.exp(best.x[noise_index]))
        self.X = X
        self._prepare(target)
        return self

    def _negative_log_likelihood(self, theta, X, target):
        """
        What a fit is scored by: how well the kernel these hyperparameters
        describe explains the data, penalized for how complex a kernel it
        takes to do it -- which is the whole point of a marginal likelihood
        over a plain least-squares fit, and what keeps a handful of points
        from being explained by a kernel so wiggly it means nothing between
        them.
        """
        dims = X.shape[1]
        length_scales = np.exp(theta[:dims])
        signal_var = np.exp(theta[dims])
        noise_var = np.exp(theta[dims + 1])
        count = X.shape[0]

        scaled = X / length_scales
        K = signal_var * np.exp(-0.5 * np.maximum(_sq_dist(scaled, scaled), 0.0))
        K[np.diag_indices_from(K)] += noise_var + _JITTER

        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            # Not a kernel worth scoring: whatever it would say about the
            # data, it does not correspond to a valid covariance.
            return 1e10

        alpha = np.linalg.solve(L.T, np.linalg.solve(L, target))
        fit_term = 0.5 * target.dot(alpha)
        complexity_term = np.sum(np.log(np.diagonal(L)))
        return float(fit_term + complexity_term + 0.5 * count * np.log(2 * np.pi))

    def _prepare(self, target):
        """The Cholesky factor and weights a prediction is read off of."""
        scaled = self.X / self.length_scales
        K = self.signal_var * np.exp(-0.5 * np.maximum(_sq_dist(scaled, scaled), 0.0))
        K[np.diag_indices_from(K)] += self.noise_var + _JITTER
        self._L = np.linalg.cholesky(K)
        self._alpha = np.linalg.solve(self._L.T, np.linalg.solve(self._L, target))

    def predict(self, X):
        """
        The posterior mean and variance at new points.

        Args:
            X (array-like): points, normalized the same way the training
                inputs were.

        Returns:
            tuple: ``(mean, variance)``, one of each per row of ``X``, back on
            the scale of the ``y`` the model was fit to.
        """
        X = np.atleast_2d(np.asarray(X, dtype=float))
        scaled_train = self.X / self.length_scales
        scaled_query = X / self.length_scales
        K_star = self.signal_var * np.exp(-0.5 * np.maximum(_sq_dist(scaled_query, scaled_train), 0.0))

        mean = K_star.dot(self._alpha) * self.y_std + self.y_mean

        v = np.linalg.solve(self._L, K_star.T)
        variance = np.maximum(self.signal_var - np.sum(v ** 2, axis=0), 0.0) * (self.y_std ** 2)
        return mean, variance

    def __repr__(self):
        return "<GaussianProcess {0}>".format(
            "fitted on {0} point(s)".format(self.X.shape[0]) if self.fitted else "unfitted"
        )
