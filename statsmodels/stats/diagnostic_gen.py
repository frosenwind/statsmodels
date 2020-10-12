# -*- coding: utf-8 -*-
"""
Created on Tue Oct  6 12:42:11 2020

Author: Josef Perktold
License: BSD-3

"""

import numpy as np
from scipy import stats
from statsmodels.stats.base import HolderTuple

def test_chisquare_binning(counts, expected, sort_var=None, bins=10,
                           df=None, ordered=False):
    """chisquare gof test with binning of data, Hosmer-Lemeshow type

    ``observed`` and ``expected`` are observation specific and should have
    observations in rows and choices in columns

    Parameters
    ----------
    counts : array_like
        Observed frequency, i.e. counts for all choices
    expected : array_like
        Expected counts or probability. If expected are counts, then they
        need to sum to the same total count as the sum of oberserved.
        If those sums are unequal and all expected values are smaller or equal
        to 1, then they are interpreted as probabilites and will be rescaled
        to match counts.
    sort_var : array_like
        1-dimensional array for binning. Groups will be formed according to
        quantiles of the sorted array ``sort_var``, so that group sizes have
        equal or approximately equal sizes.

    Returns
    -------
    Holdertuple instance
        This instance contains the results of the chisquare test and some
        information about the data

        - statistic : chisquare statistic of the goodness-of-fit test
        - pvalue : pvalue of the chisquare test
        = df : degrees of freedom of the test

    Notes
    -----
    Degrees of freedom for Hosmer-Lemeshow tests are given by

    g groups, c choices

    - binary: `df = (g - 2)` for insample,
         Stata uses `df = g` for outsample
    - multinomial: `df = (g−2) *(c−1)`, reduces to (g-2) for binary c=2,
         (Fagerland, Hosmer, Bofin SIM 2008)
    - ordinal: `df = (g - 2) * (c - 1) + (c - 2)`, reduces to (g-2) for c=2,
         (Hosmer, ... ?)

    """

    observed = np.asarray(counts)
    expected = np.asarray(expected)
    n_observed = counts.sum()
    n_expected = expected.sum()
    if not np.allclose(n_observed, n_expected, atol=1e-13):
        if np.max(expected) < 1 + 1e-13:
            # expected seems to be probability, warn and rescale
            import warnings
            warnings.warn("sum of expected and of observed differ, "
                          "rescaling ``expected``")
            expected = expected / n_expected * n_observed
        else:
            # expected doesn't look like fractions or probabilities
            raise ValueError("total counts of expected and observed differ")

    # k = 1 if observed.ndim == 1 else observed.shape[1]
    if sort_var is not None:
        argsort = np.argsort(sort_var)
    else:
        argsort = np.arange(observed.shape[0])
    #indices = [arr for arr in np.array_split(argsort, bins, axis=0)]
    indices = np.array_split(argsort, bins, axis=0)
    # in one loop, observed expected in last dimension, too messy,
    # freqs_probs = np.array([np.vstack([observed[idx].mean(0),
    #                                    expected[idx].mean(0)]).T
    #                         for idx in indices])
    freqs = np.array([observed[idx].sum(0) for idx in indices])
    probs = np.array([expected[idx].sum(0) for idx in indices])

    # chisquare test
    stat_chi2 = ((freqs - probs)**2 / probs).sum()
    if df is None:
        g, c = freqs.shape
        if ordered is True:
            df = (g - 2) * (c - 1) + (c - 2)
        else:
            df = (g - 2) * (c - 1)
    pvalue = stats.chi2.sf(stat_chi2, df)
    noncent = np.maximum(stat_chi2 - df, 0)

    res = HolderTuple(statistic=stat_chi2,
                      pvalue=pvalue,
                      df=df,
                      freqs=freqs,
                      probs=probs,
                      noncent=noncent,
                      indices=indices
                      )
    return res


def prob_larger_ordinal_choice(prob):
    """probability that observed category is larger than distribution prob

    This is a helper function for Ordinal models, where endog is a 1-dim
    categorical variable and predicted probabilities are 2-dimensional with
    observations in rows and choices in columns.

    Parameter
    ---------
    prob : array_like
        Expected probabilities for ordinal choices, e.g. from prediction of
        an ordinal model with observations in rows and choices in columns.

    Returns
    -------
    cdf_mid : ndarray
        mid cdf, i.e ``P(x < y) + 0.5 P(x=y)``
    r : ndarray
        Probability residual ``P(x > y) - P(x < y)`` for all possible choices.
        Computed as ``r = cdf_mid * 2 - 1``

    References
    ----------
    .. [2] Li, Chun, and Bryan E. Shepherd. 2012. “A New Residual for Ordinal
       Outcomes.” Biometrika 99 (2): 473–80.

    See Also
    --------
    `statsmodels.stats.nonparametric.rank_compare_2ordinal`

    """
    # similar to `nonparametric rank_compare_2ordinal`

    prob = np.asarray(prob)
    cdf = prob.cumsum(-1)
    if cdf.ndim == 1:
        cdf_ = np.concatenate(([0], cdf))
    elif cdf.ndim == 2:
        cdf_ = np.concatenate((np.zeros((len(cdf), 1)), cdf), axis=1)
    # r_1 = cdf_[..., 1:] + cdf_[..., :-1] - 1
    cdf_mid = (cdf_[..., 1:] + cdf_[..., :-1]) / 2
    r = cdf_mid * 2 - 1
    return cdf_mid, r


def prob_larger_2ordinal(probs1, probs2):
    """Stochastically large probability for two ordinal distributions

    Computes Pr(x1 > x2) + 0.5 * Pr(x1 = x2) for two ordered multinomial
    (ordinal) distributed random variables x1 and x2.

    This is vectorized with choices along last axis.
    Broadcasting if freq2 is 1-dim also seems to work correctly.

    Returns
    -------
    prob1 : float
        Probability that random draw from distribution 1 is larger than a
        random draw from distribution 2. Pr(x1 > x2) + 0.5 * Pr(x1 = x2)
    prob2 : float
        prob2 = 1 - prob1 = Pr(x1 < x2) + 0.5 * Pr(x1 = x2)
    """
#    count1 = np.asarray(count1)
#    count2 = np.asarray(count2)
#    nobs1, nobs2 = count1.sum(), count2.sum()
#    freq1 = count1 / nobs1
#    freq2 = count2 / nobs2

#     if freq1.ndim == 1:
#         freq1_ = np.concatenate(([0], freq1))
#     elif freq1.ndim == 2:
#         freq1_ = np.concatenate((np.zeros((len(freq1), 1)), freq1), axis=1)

#     if freq2.ndim == 1:
#         freq2_ = np.concatenate(([0], freq2))
#     elif freq2.ndim == 2:
#         freq2_ = np.concatenate((np.zeros((len(freq2), 1)), freq2), axis=1)

    freq1 = np.asarray(probs1)
    freq2 = np.asarray(probs2)
    # add zero at beginning of choices for cdf computation
    freq1_ = np.concatenate((np.zeros(freq1.shape[:-1] + (1,)), freq1), axis=-1)
    freq2_ = np.concatenate((np.zeros(freq2.shape[:-1] + (1,)), freq2), axis=-1)

    cdf1 = freq1_.cumsum(axis=-1)
    cdf2 = freq2_.cumsum(axis=-1)

    # mid rank cdf
    cdfm1 = (cdf1[..., 1:] + cdf1[..., :-1]) / 2
    cdfm2 = (cdf2[..., 1:] + cdf2[..., :-1]) / 2
    prob1 = (cdfm2 * freq1).sum(-1)
    prob2 = (cdfm1 * freq2).sum(-1)
    return prob1, prob2


def cov_multinomial(probs):
    """covariance matrix of multinomial distribution

    This is vectorized with choices along last axis.

    cov = diag(probs) - outer(probs, probs)

    """

    k = probs.shape[-1]
    di = np.diag_indices(k, 2)
    cov = probs[..., None] * probs[..., None, :]
    cov *= - 1
    cov[..., di[0], di[1]] += probs
    return cov


def var_multinomial(probs):
    """variance of multinomial distribution

    var = probs * (1 - probs)

    """
    var = probs * (1 - probs)
    return var
