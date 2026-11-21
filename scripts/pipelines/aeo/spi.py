"""Standardized Precipitation Index (SPI).

Method (McKee et al. 1993; Guttman 1999; WMO SPI User Guide 2012):
  1. Accumulate monthly precipitation over k months (k = 1, 3, 6, 12); the first k−1
     months are missing, and any missing month makes the accumulation missing.
  2. For each calendar month separately, take the accumulations of the reference period
     (1991–2020). Let q be the share of zero accumulations.
  3. Fit a two-parameter gamma distribution G to the non-zero reference accumulations with
     unbiased probability-weighted moments / L-moments (Hosking 1990), using Hosking's
     rational approximation for the shape (as lmom::pelgam, used by the R package SPEI).
  4. Mixed distribution for zeros: H(x) = q + (1 − q)·G(x), so H(0) = q.
  5. SPI = Φ⁻¹(H(x)), clipped to ±3.09 (as AEO's SPEI).
SPI is not computed (NaN) for a calendar month when fewer than 10 of the 30 reference
accumulations are positive: the gamma fit is not meaningful there.

Note on the R package SPEI 1.8.1: its spi() computes the zero probability but the line that
applies it is overwritten, so a zero accumulation gets G(0) = 0 and SPI = −Inf. AEO applies
the mixed distribution above; where the reference sample has no zeros the two coincide, and
the tests compare AEO with R on exactly those cases.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import gamma as gamma_dist
from scipy.stats import norm

from .spei import accumulate, ub_pwm

CLIP = 3.09
MIN_POSITIVE = 10


def pelgam(l1: float, t: float) -> tuple[float, float]:
    """Gamma shape (alpha) and scale (beta) from L-mean l1 and L-CV t (Hosking's PELGAM)."""
    if t <= 0 or t >= 1:
        raise ValueError("L-CV must be in (0, 1)")
    if t >= 0.5:
        z = 1 - t
        alpha = (0.7213 * z - 0.5947 * z * z) / (1 - 2.1817 * z + 1.2113 * z * z)
    else:
        z = np.pi * t * t
        alpha = (1 - 0.3080 * z) / (z - 0.05812 * z * z + 0.01765 * z ** 3)
    return alpha, l1 / alpha


def fit_gamma(x: np.ndarray) -> tuple[float, float]:
    """Fit gamma to positive samples x (1-D, no NaN) with unbiased PWMs."""
    w0, w1, _ = ub_pwm(np.asarray(x, float))
    l1 = float(w0)
    l2 = float(w0 - 2 * w1)  # lambda_2 = alpha_0 - 2 alpha_1
    return pelgam(l1, l2 / l1)


def spi(p: np.ndarray, months: np.ndarray, k: int, ref_mask: np.ndarray, clip: bool = True) -> np.ndarray:
    """SPI-k of a monthly precipitation series p (1-D). months: calendar month (1–12) of each
    step; ref_mask: True for steps in the reference period."""
    acc = accumulate(np.asarray(p, float), k)
    out = np.full_like(acc, np.nan)
    for m in range(1, 13):
        sel = months == m
        ref = acc[sel & ref_mask]
        ref = ref[~np.isnan(ref)]
        if ref.size == 0:
            continue
        q = float((ref == 0).sum()) / ref.size
        pos = ref[ref > 0]
        if pos.size < MIN_POSITIVE or np.std(pos) == 0:
            continue
        try:
            a, b = fit_gamma(pos)
        except ValueError:  # invalid L-moments (e.g. near-identical tiny values), as R's are.lmom.valid
            continue
        x = acc[sel]
        h = q + (1 - q) * gamma_dist.cdf(np.where(np.isnan(x), 0, x), a, scale=b)
        z = norm.ppf(h)
        z[np.isnan(x)] = np.nan
        out[sel] = np.clip(z, -CLIP, CLIP) if clip else z
    return out
