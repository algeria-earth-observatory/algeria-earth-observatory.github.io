"""Unit tests for scripts/pipelines/aeo/spei.py with SYNTHETIC series (tests only)."""
import numpy as np
import pytest
from scipy.stats import norm

from aeo.spei import CLIP, accumulate, fit_loglogistic, loglogistic_cdf, spei, ub_pwm


def test_accumulate_running_sum_and_nan():
    d = np.array([1, 2, 3, 4, 5.0])
    assert np.allclose(accumulate(d, 3)[2:], [6, 9, 12])
    assert np.isnan(accumulate(d, 3)[:2]).all()
    d[3] = np.nan
    a = accumulate(d, 2)
    assert np.isnan(a[3]) and np.isnan(a[4]) and a[2] == 5


def test_ub_pwm_matches_definition():
    rng = np.random.default_rng(1)
    x = rng.normal(10, 3, 50)
    w0, w1, w2 = ub_pwm(x)
    xs = np.sort(x)
    n = len(x)
    i = np.arange(1, n + 1)
    # alpha_s = 1/n Σ C(n-i, s)/C(n-1, s) x_(i)
    a1 = np.mean((n - i) / (n - 1) * xs)
    a2 = np.mean((n - i) * (n - i - 1) / ((n - 1) * (n - 2)) * xs)
    assert w0 == pytest.approx(x.mean())
    assert w1 == pytest.approx(a1)
    assert w2 == pytest.approx(a2)


def test_loglogistic_recovers_parameters():
    rng = np.random.default_rng(2)
    alpha, beta, gam = 40.0, 6.0, -80.0
    u = rng.uniform(size=20000)
    x = gam + alpha * (u / (1 - u)) ** (1 / beta)  # inverse CDF
    xi, a, k = fit_loglogistic(x)
    # log-logistic(alpha, beta, gamma) == GLO(xi = gamma + alpha, alpha_glo = alpha / beta, k = -1 / beta)
    assert xi == pytest.approx(gam + alpha, rel=0.05)
    assert a == pytest.approx(alpha / beta, rel=0.05)
    assert k == pytest.approx(-1 / beta, rel=0.08)
    assert loglogistic_cdf(np.median(x), xi, a, k) == pytest.approx(0.5, abs=0.01)
    xs = np.sort(x)[[200, 10000, 19800]]
    true = 1 / (1 + (alpha / (xs - gam)) ** beta)
    assert np.allclose(loglogistic_cdf(xs, xi, a, k), true, atol=0.01)


def test_spei_is_standard_normal_over_reference():
    rng = np.random.default_rng(3)
    years = 60
    months = np.tile(np.arange(1, 13), years)
    seasonal = np.tile(np.array([60, 50, 40, 20, -30, -90, -140, -130, -60, 0, 40, 60.0]), years)
    d = seasonal + rng.normal(0, 25, months.size)
    ref = np.ones(months.size, bool)
    s = spei(d, months, 3, ref)
    v = s[~np.isnan(s)]
    assert abs(v.mean()) < 0.05
    assert v.std() == pytest.approx(1, abs=0.05)
    assert np.abs(v).max() <= CLIP + 1e-9


def test_spei_grid_equals_series():
    rng = np.random.default_rng(4)
    months = np.tile(np.arange(1, 13), 40)
    d = rng.normal(-50, 30, (months.size, 2, 3))
    ref = np.arange(months.size) < 30 * 12
    grid = spei(d, months, 6, ref)
    one = spei(d[:, 1, 2], months, 6, ref)
    assert np.allclose(grid[:, 1, 2], one, equal_nan=True)


def test_drier_series_gives_negative_spei():
    rng = np.random.default_rng(5)
    months = np.tile(np.arange(1, 13), 50)
    d = rng.normal(-40, 20, months.size)
    d[-24:] -= 60  # last two years much drier than the reference
    ref = np.arange(months.size) < 30 * 12
    s = spei(d, months, 12, ref)
    assert np.nanmean(s[-12:]) < -1.5
    assert norm.cdf(np.nanmean(s[-12:])) < 0.1
