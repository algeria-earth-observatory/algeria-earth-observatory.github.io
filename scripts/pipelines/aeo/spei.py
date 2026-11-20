"""Standardised Precipitation–Evapotranspiration Index (SPEI).

Method (Vicente-Serrano, Beguería & López-Moreno 2010, J. Climate 23, 1696–1718), as in
the R package SPEI with distribution = "log-Logistic" and fit = "ub-pwm":
  1. Climatic water balance D = P − PET (mm/month).
  2. Accumulate D over k months (k = 1, 3, 6, 12); the first k−1 months are missing.
  3. For each calendar month separately, fit a three-parameter log-logistic
     distribution to the accumulated values of the reference period using
     unbiased probability-weighted moments (Hosking 1986).
  4. SPEI = Φ⁻¹(F(x)), the standard-normal quantile of the fitted CDF.
Values beyond ±3.09 (p < 0.001 or > 0.999) are clipped to ±3.09, so that values
outside the fitted support do not become infinite.
Works on 1-D series or on arrays (time first) for whole grids.
"""
from __future__ import annotations

import numpy as np
from scipy.special import gamma as G
from scipy.stats import norm

CLIP = 3.09


def accumulate(d: np.ndarray, k: int) -> np.ndarray:
    """Running k-month sum along axis 0; NaN for the first k-1 steps or if any month is NaN."""
    d = np.asarray(d, float)
    if k == 1:
        return d.copy()
    c = np.cumsum(np.nan_to_num(d), axis=0)
    out = np.full_like(d, np.nan)
    out[k - 1:] = c[k - 1:] - np.concatenate([np.zeros((1, *d.shape[1:])), c[:-k]], axis=0)
    bad = np.isnan(d).astype(int)
    nb = np.cumsum(bad, axis=0)
    nbk = np.full_like(out, 1)
    nbk[k - 1:] = nb[k - 1:] - np.concatenate([np.zeros((1, *d.shape[1:])), nb[:-k]], axis=0)
    out[nbk > 0] = np.nan
    return out


def ub_pwm(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Unbiased PWMs w0, w1, w2 (Hosking 1986) of samples along axis 0 (no NaN)."""
    x = np.sort(x, axis=0)  # ascending
    n = x.shape[0]
    i = np.arange(1, n + 1, dtype=float).reshape(-1, *([1] * (x.ndim - 1)))
    # beta_r = 1/n Σ (i-1)(i-2)...(i-r)/((n-1)...(n-r)) x_(i)  (ascending) ; alpha_s via relation
    b0 = x.mean(0)
    b1 = (((i - 1) / (n - 1)) * x).sum(0) / n
    b2 = (((i - 1) * (i - 2) / ((n - 1) * (n - 2))) * x).sum(0) / n
    # w_s = α_s = Σ_j (-1)^j C(s,j) β_j
    w0 = b0
    w1 = b0 - b1
    w2 = b0 - 2 * b1 + b2
    return w0, w1, w2


def fit_loglogistic(x: np.ndarray):
    """Generalised-logistic (GLO) parameters (xi, alpha, kappa) from unbiased PWMs.

    The three-parameter log-logistic of Vicente-Serrano et al. (2010) is fitted in
    Hosking's generalised-logistic parameterisation, as the R package SPEI (>= 1.7)
    does via lmomco::parglo; this form also handles negatively skewed samples.
    L-moments: l1 = b0, l2 = 2 b1 - b0, l3 = 6 b2 - 6 b1 + b0, t3 = l3 / l2.
    kappa = -t3; alpha = l2 sin(kappa pi) / (kappa pi); xi = l1 - alpha (1/kappa - pi / sin(kappa pi)).
    """
    w0, w1, w2 = ub_pwm(x)
    b0, b1 = w0, w0 - w1
    b2 = w2 - w0 + 2 * b1
    l1, l2, l3 = b0, 2 * b1 - b0, 6 * b2 - 6 * b1 + b0
    with np.errstate(divide="ignore", invalid="ignore"):
        k = -l3 / l2
        small = np.abs(k) < 1e-6
        kp = np.where(small, 1.0, k * np.pi)
        alpha = np.where(small, l2, l2 * np.sin(kp) / kp)
        xi = np.where(small, l1, l1 - alpha * (1 / np.where(small, 1.0, k) - np.pi / np.sin(kp)))
    return xi, alpha, k


def loglogistic_cdf(x, xi, alpha, k):
    """CDF of the generalised logistic distribution (Hosking & Wallis 1997)."""
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        small = np.abs(k) < 1e-6
        arg = 1 - k * (x - xi) / alpha
        y = np.where(small, (x - xi) / alpha, -np.log(np.where(arg > 0, arg, 1.0)) / np.where(small, 1.0, k))
        f = 1 / (1 + np.exp(-y))
        # outside the support: below the lower bound (k < 0) -> 0, above the upper bound (k > 0) -> 1
        f = np.where(~small & (arg <= 0), np.where(k > 0, 1.0, 0.0), f)
    return f


def spei(d: np.ndarray, months: np.ndarray, k: int, ref_mask: np.ndarray) -> np.ndarray:
    """SPEI-k for a series or grid.

    d        : water balance P − PET, shape (T, ...) in mm/month
    months   : calendar month (1–12) of each time step, shape (T,)
    k        : accumulation period in months
    ref_mask : boolean (T,) — time steps used to fit the distribution (e.g. 1991–2020)
    """
    acc = accumulate(d, k)
    out = np.full_like(acc, np.nan)
    for m in range(1, 13):
        sel = months == m
        ref = sel & ref_mask
        sample = acc[ref]
        ok = ~np.isnan(sample).any(0)
        if sample.shape[0] < 10:
            continue
        xi, alpha, k = fit_loglogistic(np.where(ok, sample, 0.0))
        f = loglogistic_cdf(acc[sel], xi, alpha, k)
        z = norm.ppf(np.clip(f, norm.cdf(-CLIP), norm.cdf(CLIP)))
        z = np.where(np.isnan(acc[sel]) | ~ok | ~np.isfinite(alpha) | (alpha <= 0), np.nan, z)
        out[sel] = z
    return out


CATEGORIES = [  # McKee et al. (1993) classes, widely used for SPI/SPEI
    (-np.inf, -2.0, "extremely dry"), (-2.0, -1.5, "severely dry"), (-1.5, -1.0, "moderately dry"),
    (-1.0, 1.0, "near normal"), (1.0, 1.5, "moderately wet"), (1.5, 2.0, "very wet"), (2.0, np.inf, "extremely wet"),
]
